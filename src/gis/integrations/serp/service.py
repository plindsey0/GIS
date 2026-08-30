from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    Domain,
    DomainType,
    IngestionRun,
    IngestionStatus,
    ResultOwnership,
    SerpFeatureType,
    SerpObservation,
    SerpResult,
    TrackedQuery,
)

FEATURE_MAP = {
    "organic": SerpFeatureType.ORGANIC,
    "paid": SerpFeatureType.PAID,
    "featured_snippet": SerpFeatureType.FEATURED_SNIPPET,
    "ai_overview": SerpFeatureType.AI_ANSWER,
    "people_also_ask": SerpFeatureType.PEOPLE_ALSO_ASK,
    "local_pack": SerpFeatureType.LOCAL_PACK,
    "images": SerpFeatureType.IMAGE,
    "video": SerpFeatureType.VIDEO,
    "shopping": SerpFeatureType.SHOPPING,
    "knowledge_graph": SerpFeatureType.KNOWLEDGE_PANEL,
    "top_stories": SerpFeatureType.NEWS,
    "discussions_and_forums": SerpFeatureType.DISCUSSION_FORUM,
    "related_searches": SerpFeatureType.RELATED_SEARCH,
    "sitelinks": SerpFeatureType.SITELINK,
    "maps": SerpFeatureType.MAP,
}


def normalize_query(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def normalize_url(value: str) -> tuple[str, str]:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("SERP result URL must be absolute HTTP(S)")
    hostname = parts.hostname.lower().removeprefix("www.")
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", "")), hostname


def map_feature(provider_type: str) -> SerpFeatureType:
    return FEATURE_MAP.get(
        provider_type.casefold(),
        SerpFeatureType.OTHER if provider_type else SerpFeatureType.UNKNOWN,
    )


def ownership_for_hostname(
    session: Session, site_id: uuid.UUID, hostname: str | None
) -> ResultOwnership:
    if not hostname:
        return ResultOwnership.OTHER
    domains = session.scalars(select(Domain).where(Domain.site_id == site_id)).all()
    for domain in domains:
        candidate = domain.hostname.lower().removeprefix("www.")
        if hostname == candidate or hostname.endswith(f".{candidate}"):
            return (
                ResultOwnership.KNOWN_COMPETITOR
                if domain.domain_type is DomainType.COMPETITOR
                else ResultOwnership.OWN_SITE
            )
    return ResultOwnership.OTHER


@dataclass(frozen=True)
class CostEstimate:
    queries: int
    tasks: int
    monthly_cost: Decimal
    unit_cost: Decimal
    cadence_per_month: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "queries": self.queries,
            "tasks": self.tasks,
            "monthly_cost": str(self.monthly_cost),
            "unit_cost": str(self.unit_cost),
            "cadence_per_month": str(self.cadence_per_month),
        }


def estimate_cost(queries: int, cadence: str, unit_cost: Decimal) -> CostEstimate:
    multiplier = {"ONCE": Decimal(1), "DAILY": Decimal(30), "WEEKLY": Decimal("4.345")}[
        cadence.upper()
    ]
    tasks = int((Decimal(queries) * multiplier).to_integral_value(rounding="ROUND_CEILING"))
    return CostEstimate(
        queries,
        tasks,
        (Decimal(tasks) * unit_cost).quantize(Decimal("0.0001")),
        unit_cost,
        multiplier,
    )


class SerpProvider(Protocol):
    def collect(self, query: TrackedQuery) -> dict[str, Any]: ...


class SerpCollector:
    def __init__(self, session: Session, provider: SerpProvider) -> None:
        self.session, self.provider = session, provider

    def sync(self, connection_id: uuid.UUID, tracked_query: TrackedQuery) -> IngestionRun:
        connection = self.session.get(DataSourceConnection, connection_id)
        if not connection or connection.site_id != tracked_query.site_id:
            raise ValueError("SERP connection/query scope mismatch")
        source = self.session.get(DataSource, connection.data_source_id)
        policy_id = connection.rights_policy_id or (
            source.default_rights_policy_id if source else None
        )
        policy = self.session.get(DataRightsPolicy, policy_id) if policy_id else None
        if not source or not policy:
            raise ValueError("SERP source and rights policy are required")
        now = datetime.now(timezone.utc)
        run = IngestionRun(
            tenant_id=connection.tenant_id,
            site_id=connection.site_id,
            data_source_connection_id=connection.id,
            started_at=now,
            status=IngestionStatus.RUNNING,
            rights_policy_id=policy.id,
            acquisition_method=source.acquisition_method,
            collector_name="gis.integrations.serp",
            collector_version="1",
            schema_version="1",
            source_metadata={
                "tracked_query_id": str(tracked_query.id),
                "requested_depth": tracked_query.requested_depth,
            },
        )
        self.session.add(run)
        self.session.flush()
        try:
            payload = self.provider.collect(tracked_query)
            task = payload.get("tasks", [{}])[0]
            result = task.get("result", [{}])[0]
            observed_at = datetime.fromisoformat(
                result.get("datetime", now.isoformat()).replace("Z", "+00:00")
            )
            identity = [
                str(tracked_query.id),
                observed_at.date().isoformat(),
                tracked_query.device,
                tracked_query.location_code,
            ]
            key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            current = self.session.scalar(
                select(SerpObservation).where(
                    SerpObservation.observation_key == key, SerpObservation.effective_end.is_(None)
                )
            )
            if current:
                current.effective_end = now
            observation = SerpObservation(
                tenant_id=connection.tenant_id,
                site_id=tracked_query.site_id,
                tracked_query_id=tracked_query.id,
                ingestion_run_id=run.id,
                data_source_connection_id=connection.id,
                rights_policy_id=policy.id,
                rights_policy_version=policy.policy_version,
                provider_task_id=task.get("id"),
                observation_key=key,
                observed_date=observed_at.date(),
                observed_at=observed_at,
                search_engine=tracked_query.search_engine,
                query_text=tracked_query.query_text,
                normalized_query=tracked_query.normalized_query,
                country_code=tracked_query.country_code,
                location_code=tracked_query.location_code,
                location_name=tracked_query.location_name,
                language_code=tracked_query.language_code,
                device=tracked_query.device,
                requested_depth=tracked_query.requested_depth,
                effective_start=now,
            )
            self.session.add(observation)
            self.session.flush()
            received = 0
            for item in result.get("items", []):
                rank = item.get("rank_absolute")
                provider_type = str(item.get("type", ""))
                if not isinstance(rank, int) or rank < 1:
                    continue
                url = item.get("url")
                normalized = host = None
                if url:
                    try:
                        normalized, host = normalize_url(str(url))
                    except ValueError:
                        continue
                feature = map_feature(provider_type)
                self.session.add(
                    SerpResult(
                        serp_observation_id=observation.id,
                        rank_absolute=rank,
                        rank_group=item.get("rank_group"),
                        feature_type=feature,
                        provider_type=provider_type or "unknown",
                        url=url,
                        normalized_url=normalized,
                        hostname=host,
                        title=item.get("title"),
                        snippet=item.get("description"),
                        breadcrumb=item.get("breadcrumb"),
                        is_paid=feature is SerpFeatureType.PAID,
                        is_organic=feature is SerpFeatureType.ORGANIC,
                        is_feature=feature not in {SerpFeatureType.ORGANIC, SerpFeatureType.PAID},
                        ownership=ownership_for_hostname(self.session, tracked_query.site_id, host),
                        provider_metadata={"xpath": item.get("xpath")},
                    )
                )
                received += 1
            run.records_received = received
            run.records_inserted = received
            run.status = IngestionStatus.SUCCEEDED
            run.completed_at = datetime.now(timezone.utc)
            run.source_metadata = {
                **run.source_metadata,
                "provider_task_id": task.get("id"),
                "provider_cost": task.get("cost"),
            }
        except Exception as error:
            run.status = IngestionStatus.FAILED
            run.error_count = 1
            run.error_summary = type(error).__name__
            run.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        return run
