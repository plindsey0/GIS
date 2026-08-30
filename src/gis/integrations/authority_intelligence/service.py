from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.authority_intelligence.analysis import (
    ANCHOR_METHOD,
    ANCHOR_VERSION,
    canonical_url,
    classify_anchor,
    follow_state,
    link_identity,
    link_type,
    normalize_domain,
)
from gis.integrations.authority_intelligence.provider import (
    AuthorityCollection,
    AuthorityMetric,
    AuthorityProvider,
    AuthorityRequest,
    BacklinkRecord,
)
from gis.models import (
    AuthorityLinkState,
    AuthorityMetricDefinition,
    AuthorityMetricObservation,
    AuthorityObservation,
    AuthorityOwnership,
    AuthorityTargetType,
    BacklinkObservation,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    Domain,
    DomainType,
    EventSemanticClass,
    IngestionRun,
    IngestionStatus,
    PermittedUse,
    ReferringDomainObservation,
    Site,
)
from gis.provenance.service import assert_use_allowed, evaluate_connection_use

COLLECTOR_VERSION = "1.0.0"


class AuthorityCollector:
    def __init__(self, session: Session, provider: AuthorityProvider) -> None:
        self.session, self.provider = session, provider

    def collect(
        self,
        connection_id: uuid.UUID,
        site_id: uuid.UUID,
        request: AuthorityRequest,
        *,
        estimated_cost: Decimal = Decimal("0"),
    ) -> IngestionRun:
        request.validate()
        connection = self.session.get(DataSourceConnection, connection_id)
        site = self.session.get(Site, site_id)
        if not connection or not site or connection.tenant_id != site.tenant_id:
            raise ValueError("authority connection/site scope mismatch")
        if connection.site_id and connection.site_id != site.id:
            raise ValueError("site-scoped authority connection cannot collect another site")
        source = self.session.get(DataSource, connection.data_source_id)
        policy_id = connection.rights_policy_id or (
            source.default_rights_policy_id if source else None
        )
        policy = self.session.get(DataRightsPolicy, policy_id) if policy_id else None
        if not source or not policy:
            raise ValueError("authority source and rights policy are required")
        # Rights checks occur before the provider is invoked. UNKNOWN is not permission.
        assert_use_allowed(
            evaluate_connection_use(self.session, connection, PermittedUse.NORMALIZED_RETENTION)
        )
        assert_use_allowed(
            evaluate_connection_use(self.session, connection, PermittedUse.COMMERCIAL_USE)
        )
        if request.retain_raw_anchor:
            assert_use_allowed(
                evaluate_connection_use(self.session, connection, PermittedUse.RAW_RETENTION)
            )

        normalized_target, target_domain = self._target(request)
        ownership = self._ownership(site, target_domain)
        now = datetime.now(timezone.utc)
        run = IngestionRun(
            tenant_id=site.tenant_id,
            site_id=site.id,
            data_source_connection_id=connection.id,
            started_at=now,
            status=IngestionStatus.RUNNING,
            rights_policy_id=policy.id,
            acquisition_method=source.acquisition_method,
            collector_name="gis.integrations.authority_intelligence",
            collector_version=COLLECTOR_VERSION,
            schema_version="1",
            requested_start_at=request.start_at,
            requested_end_at=request.end_at,
            source_metadata={
                "target_type": request.target_type.value,
                "target": normalized_target,
                "row_limit": request.row_limit,
                "page_limit": request.page_limit,
                "estimated_cost": str(estimated_cost),
            },
        )
        self.session.add(run)
        self.session.flush()
        savepoint = self.session.begin_nested()
        try:
            collection = self.provider.collect(request)
            payload = self._content_payload(collection)
            content_hash = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()
            identity = [
                str(site.id),
                collection.provider,
                request.target_type.value,
                normalized_target,
                collection.observed_at.date().isoformat(),
                collection.observation_scope,
            ]
            observation_key = hashlib.sha256(
                json.dumps(identity, separators=(",", ":")).encode()
            ).hexdigest()
            current = self.session.scalar(
                select(AuthorityObservation).where(
                    AuthorityObservation.observation_key == observation_key,
                    AuthorityObservation.effective_end.is_(None),
                )
            )
            if current and current.content_hash == content_hash:
                run.status = IngestionStatus.SUCCEEDED
                run.records_received = len(collection.metrics) + len(collection.backlinks)
                run.completed_at = datetime.now(timezone.utc)
                run.source_metadata = {
                    **run.source_metadata,
                    "idempotent_replay": True,
                    "provider_cost": str(collection.cost) if collection.cost is not None else None,
                }
                savepoint.commit()
                self.session.commit()
                return run
            if current:
                current.effective_end = now
                run.records_updated = 1
            observation = AuthorityObservation(
                tenant_id=site.tenant_id,
                organization_id=site.organization_id,
                site_id=site.id,
                data_source_connection_id=connection.id,
                ingestion_run_id=run.id,
                rights_policy_id=policy.id,
                rights_policy_version=policy.policy_version,
                provider=collection.provider,
                provider_task_id=collection.task_id,
                target_type=request.target_type,
                target_domain=target_domain,
                target_url=normalized_target
                if request.target_type is AuthorityTargetType.PAGE
                else None,
                ownership=ownership,
                observed_date=collection.observed_at.date(),
                observed_at=collection.observed_at,
                observation_scope=collection.observation_scope,
                completeness=collection.completeness,
                observation_key=observation_key,
                content_hash=content_hash,
                request_count=collection.request_count,
                records_received=len(collection.metrics) + len(collection.backlinks),
                provider_reported_cost=collection.cost,
                estimated_cost=estimated_cost,
                cost_currency=collection.currency,
                provider_metadata=collection.metadata,
                effective_start=now,
            )
            self.session.add(observation)
            self.session.flush()
            self._metrics(observation, collection.metrics)
            self._backlinks(observation, collection.backlinks, request.retain_raw_anchor)
            run.status = IngestionStatus.SUCCEEDED
            run.records_received = len(collection.metrics) + len(collection.backlinks)
            run.records_inserted = 1 + len(collection.metrics) + len(collection.backlinks)
            run.completed_at = datetime.now(timezone.utc)
            run.source_metadata = {
                **run.source_metadata,
                "provider": collection.provider,
                "provider_task_id": collection.task_id,
                "provider_cost": str(collection.cost) if collection.cost is not None else None,
                "currency": collection.currency,
            }
            savepoint.commit()
        except Exception as error:
            savepoint.rollback()
            run.status = IngestionStatus.FAILED
            run.error_count = 1
            run.error_summary = f"{type(error).__name__}: {error}"[:1000]
            run.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        return run

    def _target(self, request: AuthorityRequest) -> tuple[str, str]:
        if request.target_type is AuthorityTargetType.DOMAIN:
            domain = normalize_domain(request.target)
            return domain, domain
        return canonical_url(request.target)

    def _ownership(self, site: Site, domain: str) -> AuthorityOwnership:
        row = self.session.scalar(
            select(Domain).where(
                Domain.tenant_id == site.tenant_id,
                Domain.site_id == site.id,
                Domain.hostname == domain,
            )
        )
        if row and row.domain_type in {DomainType.PRIMARY, DomainType.ALIAS, DomainType.REDIRECT}:
            return AuthorityOwnership.OWNED
        if row and row.domain_type is DomainType.COMPETITOR:
            return AuthorityOwnership.COMPETITOR
        return AuthorityOwnership.OTHER

    def _metrics(
        self, observation: AuthorityObservation, metrics: tuple[AuthorityMetric, ...]
    ) -> None:
        for raw in metrics:
            metric = raw
            definition = self.session.scalar(
                select(AuthorityMetricDefinition).where(
                    AuthorityMetricDefinition.provider == metric.provider,
                    AuthorityMetricDefinition.metric_key == metric.key,
                )
            )
            if definition is None:
                definition = AuthorityMetricDefinition(
                    provider=metric.provider,
                    metric_key=metric.key,
                    display_name=metric.name,
                    scale_min=metric.scale_min,
                    scale_max=metric.scale_max,
                    unit=metric.unit,
                    methodology_version=metric.methodology_version,
                    semantic_class=metric.semantic_class,
                )
                self.session.add(definition)
                self.session.flush()
            self.session.add(
                AuthorityMetricObservation(
                    authority_observation_id=observation.id,
                    metric_definition_id=definition.id,
                    metric_provider=metric.provider,
                    metric_key=metric.key,
                    metric_name=metric.name,
                    metric_value=metric.value,
                    scale_min=metric.scale_min,
                    scale_max=metric.scale_max,
                    unit=metric.unit,
                    methodology_version=metric.methodology_version,
                    semantic_class=metric.semantic_class,
                    provider_metadata=metric.metadata,
                )
            )

    def _backlinks(
        self,
        observation: AuthorityObservation,
        backlinks: tuple[BacklinkRecord, ...],
        retain_raw_anchor: bool,
    ) -> None:
        domains: dict[str, list[tuple[BacklinkRecord, BacklinkObservation]]] = defaultdict(list)
        for raw in backlinks:
            source_url, source_domain = canonical_url(raw.source_url)
            target_url, target_domain = canonical_url(raw.target_url)
            classification, confidence = classify_anchor(raw.anchor_text, target_domain, target_url)
            normalized_anchor = " ".join((raw.anchor_text or "").split()).casefold()
            follow = follow_state(raw.rel)
            stored = BacklinkObservation(
                authority_observation_id=observation.id,
                provider_record_id=raw.provider_record_id,
                link_identity=link_identity(
                    raw.provider_record_id, source_url, target_url, raw.link_type
                ),
                source_url=source_url,
                source_domain=source_domain,
                target_url=target_url,
                target_domain=target_domain,
                link_state=raw.state,
                follow_state=follow,
                sponsored="sponsored" in raw.rel,
                ugc="ugc" in raw.rel,
                link_type=link_type(raw.link_type),
                anchor_text=raw.anchor_text if retain_raw_anchor else None,
                anchor_hash=hashlib.sha256(normalized_anchor.encode()).hexdigest()
                if normalized_anchor
                else None,
                anchor_classification=classification,
                anchor_method=ANCHOR_METHOD,
                anchor_method_version=ANCHOR_VERSION,
                anchor_confidence=confidence,
                first_seen_at=raw.first_seen_at,
                last_seen_at=raw.last_seen_at,
                semantic_class=raw.semantic_class,
                provider_metadata=raw.metadata,
            )
            self.session.add(stored)
            domains[source_domain].append((raw, stored))
        for domain, rows in sorted(domains.items()):
            followed = sum(1 for _, stored in rows if stored.follow_state.value == "FOLLOWED")
            nofollow = sum(1 for _, stored in rows if stored.follow_state.value == "NOFOLLOW")
            states = {raw.state for raw, _ in rows}
            state = next(iter(states)) if len(states) == 1 else observation_state(rows)
            seen = [raw.first_seen_at for raw, _ in rows if raw.first_seen_at]
            last = [raw.last_seen_at for raw, _ in rows if raw.last_seen_at]
            self.session.add(
                ReferringDomainObservation(
                    authority_observation_id=observation.id,
                    referring_domain=domain,
                    target_domain=observation.target_domain,
                    backlink_count=len(rows),
                    followed_count=followed,
                    nofollow_count=nofollow,
                    first_seen_at=min(seen) if seen else None,
                    last_seen_at=max(last) if last else None,
                    link_state=state,
                    semantic_class=EventSemanticClass.GIS_DERIVED,
                    provider_metadata={"derivation": "grouped normalized backlink observations"},
                )
            )

    @staticmethod
    def _content_payload(collection: AuthorityCollection) -> dict[str, object]:
        return {
            "provider": collection.provider,
            "observed_at": collection.observed_at,
            "metrics": collection.metrics,
            "backlinks": collection.backlinks,
            "completeness": collection.completeness,
            "scope": collection.observation_scope,
        }


def observation_state(
    rows: list[tuple[BacklinkRecord, BacklinkObservation]],
) -> AuthorityLinkState:
    if any(raw.state is AuthorityLinkState.OBSERVED_NEW for raw, _ in rows):
        return AuthorityLinkState.OBSERVED_NEW
    if all(raw.state is AuthorityLinkState.OBSERVED_LOST for raw, _ in rows):
        return AuthorityLinkState.OBSERVED_LOST
    if any(raw.state is AuthorityLinkState.OBSERVED_ACTIVE for raw, _ in rows):
        return AuthorityLinkState.OBSERVED_ACTIVE
    return AuthorityLinkState.UNKNOWN
