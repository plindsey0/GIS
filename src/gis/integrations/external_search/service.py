from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.external_search.dataforseo import (
    ProviderCollection,
    SearchRequest,
    normalize_domain,
)
from gis.models import (
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    ExternalCompetitorObservation,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    IngestionRun,
    IngestionStatus,
    Site,
)
from gis.provider_control.service import ProviderControlService


class ExternalSearchProvider(Protocol):
    def collect(self, request: SearchRequest) -> ProviderCollection: ...


def normalize_keyword(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def normalize_ranking_url(value: str | None) -> tuple[str | None, str]:
    if not value:
        return None, ""
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("ranking URL must be absolute HTTP(S)")
    normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", "", ""))
    return normalized, normalize_domain(parts.hostname)


def _decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


class ExternalSearchCollector:
    def __init__(self, session: Session, provider: ExternalSearchProvider) -> None:
        self.session, self.provider = session, provider

    def sync(
        self,
        connection_id: uuid.UUID,
        site_id: uuid.UUID,
        request: SearchRequest,
        *,
        estimated_cost: Decimal | None = None,
    ) -> IngestionRun:
        connection = self.session.get(DataSourceConnection, connection_id)
        site = self.session.get(Site, site_id)
        if not connection or not site or connection.tenant_id != site.tenant_id:
            raise ValueError("external-search connection/site scope mismatch")
        if connection.site_id is not None and connection.site_id != site.id:
            raise ValueError("site-scoped connection cannot collect for another site")
        source = self.session.get(DataSource, connection.data_source_id)
        policy_id = connection.rights_policy_id or (
            source.default_rights_policy_id if source else None
        )
        policy = self.session.get(DataRightsPolicy, policy_id) if policy_id else None
        if not source or not policy:
            raise ValueError("external-search source and rights policy are required")
        control = ProviderControlService(self.session)
        collection_policy = control.policy(
            site.tenant_id, site.id, control.provider("dataforseo").id
        )
        if collection_policy and collection_policy.data_source_connection_id != connection.id:
            raise ValueError("Collection must use the connection selected by the provider policy")
        preflight = control.preflight(
            site.tenant_id,
            site.id,
            "dataforseo",
            "DOMAIN_SEARCH_INTELLIGENCE",
            [normalize_domain(request.target_domain)],
            1,
            Decimal("1"),
            reserve=True,
            estimated_cost_override=estimated_cost,
        )
        if not preflight.can_execute or preflight.reservation_id is None:
            raise ValueError(
                "provider collection blocked: " + ", ".join(preflight.blocking_reasons)
            )
        reservation_id = preflight.reservation_id
        now = datetime.now(timezone.utc)
        run = IngestionRun(
            tenant_id=site.tenant_id,
            site_id=site.id,
            data_source_connection_id=connection.id,
            started_at=now,
            status=IngestionStatus.RUNNING,
            rights_policy_id=policy.id,
            acquisition_method=source.acquisition_method,
            collector_name="gis.integrations.external_search",
            collector_version="1",
            schema_version="1",
            source_metadata={
                "observation_type": request.observation_type,
                "target_domain": normalize_domain(request.target_domain),
                "limit": request.limit,
            },
        )
        self.session.add(run)
        self.session.flush()
        # Keep the usage reservation durable before an external charge can occur.
        self.session.commit()
        savepoint = self.session.begin_nested()
        try:
            collection = self.provider.collect(request)
            content_hash = hashlib.sha256(
                json.dumps(collection.items, sort_keys=True, default=str).encode()
            ).hexdigest()
            identity = [
                str(site.id),
                request.observation_type,
                normalize_domain(request.target_domain),
                request.location_code,
                request.location_name,
                request.language_code,
                request.device,
                collection.observed_at.date().isoformat(),
            ]
            observation_key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            current = self.session.scalar(
                select(ExternalSearchObservation).where(
                    ExternalSearchObservation.observation_key == observation_key,
                    ExternalSearchObservation.effective_end.is_(None),
                )
            )
            if current and current.content_hash == content_hash:
                run.status = IngestionStatus.SUCCEEDED
                run.records_received = len(collection.items)
                run.records_inserted = 0
                run.completed_at = datetime.now(timezone.utc)
                run.source_metadata = {**run.source_metadata, "idempotent_replay": True}
                control.reconcile(
                    reservation_id,
                    actual_cost=collection.cost,
                    semantics="PROVIDER_REPORTED" if collection.cost is not None else "ESTIMATED",
                    status="SUCCEEDED",
                    ingestion_run_id=run.id,
                )
                savepoint.commit()
                self.session.commit()
                return run
            if current:
                current.effective_end = now
            observation = ExternalSearchObservation(
                tenant_id=site.tenant_id,
                site_id=site.id,
                ingestion_run_id=run.id,
                data_source_connection_id=connection.id,
                rights_policy_id=policy.id,
                rights_policy_version=policy.policy_version,
                observation_type=request.observation_type,
                target_domain=normalize_domain(request.target_domain),
                country_code=request.country_code,
                location_code=request.location_code,
                location_name=request.location_name,
                language_code=request.language_code,
                device=request.device,
                observed_date=collection.observed_at.date(),
                observed_at=collection.observed_at,
                observation_key=observation_key,
                content_hash=content_hash,
                provider_task_id=collection.task_id,
                request_count=1,
                items_returned=len(collection.items),
                provider_reported_cost=collection.cost,
                estimated_cost=estimated_cost,
                cost_metadata={"semantics": "PROVIDER_REPORTED_AND_PRE_REQUEST_ESTIMATE"},
                provider_metadata=collection.metadata,
                effective_start=now,
            )
            self.session.add(observation)
            self.session.flush()
            if request.observation_type == "ranked_keywords":
                self._rankings(observation, collection)
            else:
                self._competitors(observation, collection)
            run.status = IngestionStatus.SUCCEEDED
            run.records_received = len(collection.items)
            run.records_inserted = len(collection.items)
            run.completed_at = datetime.now(timezone.utc)
            run.source_metadata = {
                **run.source_metadata,
                "provider_task_id": collection.task_id,
                "provider_cost": str(collection.cost) if collection.cost is not None else None,
            }
            control.reconcile(
                reservation_id,
                actual_cost=collection.cost,
                semantics="PROVIDER_REPORTED" if collection.cost is not None else "ESTIMATED",
                status="SUCCEEDED",
                ingestion_run_id=run.id,
            )
            savepoint.commit()
        except Exception as error:
            savepoint.rollback()
            run.status = IngestionStatus.FAILED
            run.error_count = 1
            run.error_summary = f"{type(error).__name__}: {error}"[:1000]
            run.completed_at = datetime.now(timezone.utc)
            control.reconcile(
                reservation_id,
                actual_cost=None,
                semantics="UNKNOWN",
                status="FAILED",
                ingestion_run_id=run.id,
            )
        self.session.commit()
        return run

    def _rankings(
        self, observation: ExternalSearchObservation, collection: ProviderCollection
    ) -> None:
        for item in collection.items:
            keyword_data = item.get("keyword_data") or {}
            keyword_info = keyword_data.get("keyword_info") or {}
            serp = (item.get("ranked_serp_element") or {}).get("serp_item") or {}
            keyword = str(keyword_data.get("keyword") or "").strip()
            position = serp.get("rank_absolute")
            if not keyword or not isinstance(position, int) or position < 1:
                raise ValueError("malformed ranked-keyword item")
            normalized_url, domain = normalize_ranking_url(serp.get("url"))
            domain = domain or observation.target_domain
            properties = keyword_data.get("keyword_properties") or {}
            intent = keyword_data.get("search_intent_info") or {}
            self.session.add(
                ExternalKeywordRanking(
                    external_search_observation_id=observation.id,
                    keyword=keyword,
                    normalized_keyword=normalize_keyword(keyword),
                    ranking_domain=domain,
                    ranking_url=serp.get("url"),
                    normalized_url=normalized_url or "",
                    position=position,
                    prior_position=serp.get("previous_rank_absolute"),
                    ranking_type=str(serp.get("type") or "organic"),
                    search_volume=keyword_info.get("search_volume"),
                    cpc=_decimal(keyword_info.get("cpc")),
                    paid_competition=_decimal(keyword_info.get("competition")),
                    competition_index=keyword_info.get("competition_index"),
                    search_intent=intent.get("main_intent"),
                    keyword_difficulty=_decimal(properties.get("keyword_difficulty")),
                    estimated_traffic=_decimal(serp.get("etv")),
                    estimated_traffic_share=_decimal(serp.get("estimated_traffic_volume")),
                    monthly_searches=keyword_info.get("monthly_searches") or [],
                    metric_semantics={
                        "search_volume": "PROVIDER_ESTIMATED",
                        "cpc": "PROVIDER_DERIVED",
                        "keyword_difficulty": "PROVIDER_DERIVED_DATAFORSEO",
                        "estimated_traffic": "PROVIDER_ESTIMATED",
                    },
                    provider_metadata={"rank_group": serp.get("rank_group")},
                )
            )

    def _competitors(
        self, observation: ExternalSearchObservation, collection: ProviderCollection
    ) -> None:
        for item in collection.items:
            domain = normalize_domain(str(item.get("domain") or ""))
            metrics = (item.get("full_domain_metrics") or {}).get("organic") or {}
            shared = item.get("intersections")
            target_count = item.get("target_keywords")
            competitor_count = metrics.get("count")
            strength = None
            if (
                isinstance(shared, int)
                and isinstance(target_count, int)
                and isinstance(competitor_count, int)
            ):
                strength = Decimal(shared) / Decimal(max(target_count, competitor_count, 1))
            self.session.add(
                ExternalCompetitorObservation(
                    external_search_observation_id=observation.id,
                    competitor_domain=domain,
                    target_keyword_count=target_count,
                    competitor_keyword_count=competitor_count,
                    shared_keyword_count=shared,
                    provider_relevance=_decimal(item.get("relevance")),
                    provider_estimated_traffic=_decimal(metrics.get("etv")),
                    provider_visibility=_decimal(item.get("visibility")),
                    gis_competitive_strength=strength,
                    metric_semantics={
                        "relevance": "PROVIDER_DERIVED",
                        "estimated_traffic": "PROVIDER_ESTIMATED",
                        "gis_competitive_strength": "GIS_DERIVED_SHARED_OVER_MAX_FOOTPRINT",
                    },
                    provider_metadata={
                        "average_position": item.get("avg_position"),
                        "rank_distribution": metrics.get("pos_1"),
                    },
                )
            )
