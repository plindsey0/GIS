from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.content_intelligence.extraction import normalize_url
from gis.integrations.content_intelligence.retrieval import ContentRetriever
from gis.integrations.technology_intelligence.detection import detect_technologies
from gis.integrations.technology_intelligence.signatures import (
    SIGNATURE_REGISTRY_VERSION,
    TECHNOLOGIES,
)
from gis.models import (
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    IngestionRun,
    IngestionStatus,
    PermittedUse,
    Site,
    Technology,
    TechnologyAlias,
    TechnologyDetection,
    TechnologyEvidence,
    TechnologyObservation,
)
from gis.provenance.service import assert_use_allowed, evaluate_connection_use


def normalize_technology_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def technology_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return slug[:240] or "unknown_technology"


def sync_technology_registry(session: Session) -> None:
    for definition in TECHNOLOGIES:
        technology = session.scalar(select(Technology).where(Technology.slug == definition.slug))
        if technology is None:
            technology = Technology(
                slug=definition.slug,
                name=definition.name,
                vendor=definition.vendor,
                category=definition.category,
                metadata_json={"registry_version": SIGNATURE_REGISTRY_VERSION},
            )
            session.add(technology)
            session.flush()
        for alias in (definition.name, *definition.aliases):
            normalized = normalize_technology_name(alias)
            existing = session.scalar(
                select(TechnologyAlias).where(
                    TechnologyAlias.source_key == "canonical",
                    TechnologyAlias.normalized_alias == normalized,
                )
            )
            if existing is None:
                session.add(
                    TechnologyAlias(
                        technology_id=technology.id,
                        source_key="canonical",
                        alias=alias,
                        normalized_alias=normalized,
                    )
                )
    session.flush()


def resolve_provider_technology(
    session: Session,
    provider_name: str,
    *,
    source_key: str,
    provider_category: str | None = None,
    provider_identifier: str | None = None,
) -> Technology:
    normalized = normalize_technology_name(provider_name)
    alias = session.scalar(
        select(TechnologyAlias).where(
            TechnologyAlias.source_key.in_((source_key, "canonical")),
            TechnologyAlias.normalized_alias == normalized,
        )
    )
    if alias:
        technology = session.get(Technology, alias.technology_id)
        if technology:
            return technology
    slug = technology_slug(provider_name)
    technology = session.scalar(select(Technology).where(Technology.slug == slug))
    if technology is None:
        technology = Technology(
            slug=slug,
            name=provider_name.strip(),
            category=provider_category or "UNKNOWN",
            metadata_json={"unreviewed_provider_identity": True},
        )
        session.add(technology)
        session.flush()
    session.add(
        TechnologyAlias(
            technology_id=technology.id,
            source_key=source_key,
            alias=provider_name,
            normalized_alias=normalized,
            provider_identifier=provider_identifier,
        )
    )
    session.flush()
    return technology


class TechnologyCollector:
    def __init__(self, session: Session, retriever: ContentRetriever) -> None:
        self.session, self.retriever = session, retriever

    def collect(
        self,
        connection_id: uuid.UUID,
        site_id: uuid.UUID,
        url: str,
        *,
        observation_scope: str = "PAGE",
        estimated_cost: Decimal | None = Decimal("0"),
    ) -> IngestionRun:
        connection = self.session.get(DataSourceConnection, connection_id)
        site = self.session.get(Site, site_id)
        if not connection or not site or connection.tenant_id != site.tenant_id:
            raise ValueError("technology connection/site scope mismatch")
        if connection.site_id is not None and connection.site_id != site.id:
            raise ValueError("site-scoped connection cannot collect for another site")
        if observation_scope not in {"PAGE", "SITE", "DOMAIN"}:
            raise ValueError("invalid technology observation scope")
        source = self.session.get(DataSource, connection.data_source_id)
        policy_id = connection.rights_policy_id or (
            source.default_rights_policy_id if source else None
        )
        policy = self.session.get(DataRightsPolicy, policy_id) if policy_id else None
        if not source or not policy:
            raise ValueError("technology source and rights policy are required")
        assert_use_allowed(
            evaluate_connection_use(self.session, connection, PermittedUse.NORMALIZED_RETENTION)
        )
        sync_technology_registry(self.session)
        normalized_requested, requested_domain, _ = normalize_url(url)
        now = datetime.now(timezone.utc)
        run = IngestionRun(
            tenant_id=site.tenant_id,
            site_id=site.id,
            data_source_connection_id=connection.id,
            started_at=now,
            status=IngestionStatus.RUNNING,
            rights_policy_id=policy.id,
            acquisition_method=source.acquisition_method,
            collector_name="gis.integrations.technology_intelligence",
            collector_version="1",
            schema_version="1",
            source_metadata={
                "url": normalized_requested,
                "scope": observation_scope,
                "signature_version": SIGNATURE_REGISTRY_VERSION,
            },
        )
        self.session.add(run)
        self.session.flush()
        savepoint = self.session.begin_nested()
        try:
            result = self.retriever.retrieve(normalized_requested)
            normalized_resolved, domain, _ = normalize_url(result.resolved_url)
            detections = detect_technologies(result)
            content_material = {
                "body": hashlib.sha256(result.body).hexdigest(),
                "headers": result.headers,
                "signature_version": SIGNATURE_REGISTRY_VERSION,
            }
            content_hash = hashlib.sha256(
                json.dumps(content_material, sort_keys=True).encode()
            ).hexdigest()
            identity = [
                str(site.id),
                normalized_requested,
                observation_scope,
                result.retrieved_at.date().isoformat(),
            ]
            observation_key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
            current = self.session.scalar(
                select(TechnologyObservation).where(
                    TechnologyObservation.observation_key == observation_key,
                    TechnologyObservation.effective_end.is_(None),
                )
            )
            if current and current.content_hash == content_hash:
                run.status = IngestionStatus.SUCCEEDED
                run.records_received = len(detections)
                run.completed_at = datetime.now(timezone.utc)
                run.source_metadata = {**run.source_metadata, "idempotent_replay": True}
                savepoint.commit()
                self.session.commit()
                return run
            if current:
                current.effective_end = now
            owned_domain = normalize_url(site.canonical_url)[1]
            observation = TechnologyObservation(
                tenant_id=site.tenant_id,
                organization_id=site.organization_id,
                site_id=site.id,
                data_source_connection_id=connection.id,
                ingestion_run_id=run.id,
                rights_policy_id=policy.id,
                rights_policy_version=policy.policy_version,
                domain=domain,
                requested_url=url,
                normalized_url=normalized_resolved,
                ownership_class="OWNED" if domain == owned_domain else "COMPETITOR",
                observation_scope=observation_scope,
                observed_at=result.retrieved_at,
                collected_at=result.retrieved_at,
                collection_status=("SUCCESS" if 200 <= result.status_code < 300 else "HTTP_ERROR"),
                http_status=result.status_code,
                render_mode="RAW_HTTP",
                content_hash=content_hash,
                observation_key=observation_key,
                request_count=1,
                estimated_cost=estimated_cost,
                cost_currency="USD",
                signature_version=SIGNATURE_REGISTRY_VERSION,
                collection_metadata={
                    "detection_count": len(detections),
                    "missing_detection_semantics": "NOT_OBSERVED_NOT_ABSENT",
                    "javascript_rendered": False,
                    "truncated": result.truncated,
                },
                effective_start=now,
            )
            self.session.add(observation)
            self.session.flush()
            definitions = {item.slug: item for item in TECHNOLOGIES}
            for item in detections:
                definition = definitions[item.technology_slug]
                technology = self.session.scalar(
                    select(Technology).where(Technology.slug == item.technology_slug)
                )
                if not technology:
                    raise ValueError("signature technology is not registered")
                detection = TechnologyDetection(
                    observation_id=observation.id,
                    technology_id=technology.id,
                    provider_technology_name=definition.name,
                    provider_category=definition.category,
                    presence_status="PRESENT",
                    detection_scope=item.scope,
                    confidence=item.confidence,
                    semantic_class=item.semantic_class,
                    detection_method="DIRECT_SIGNATURE_REGISTRY",
                    metadata_json={"signature_count": len(item.evidence)},
                )
                self.session.add(detection)
                self.session.flush()
                for evidence in item.evidence:
                    self.session.add(
                        TechnologyEvidence(
                            detection_id=detection.id,
                            signature_key=evidence.signature_key,
                            signature_version=SIGNATURE_REGISTRY_VERSION,
                            evidence_type=evidence.evidence_type,
                            match_target=evidence.match_target,
                            evidence_value=evidence.evidence_value,
                            evidence_hash=evidence.evidence_hash,
                            semantic_class=evidence.semantic_class,
                            confidence=evidence.confidence,
                        )
                    )
            run.status = IngestionStatus.SUCCEEDED
            run.records_received = len(detections)
            run.records_inserted = len(detections)
            run.completed_at = datetime.now(timezone.utc)
            savepoint.commit()
        except Exception as error:
            savepoint.rollback()
            run.status = IngestionStatus.FAILED
            run.error_count = 1
            run.error_summary = f"{type(error).__name__}: {error}"[:1000]
            run.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        return run


def technology_changes(
    session: Session, site_id: uuid.UUID, domain: str
) -> list[dict[str, object]]:
    observations = session.scalars(
        select(TechnologyObservation)
        .where(
            TechnologyObservation.site_id == site_id,
            TechnologyObservation.domain == domain.casefold(),
            TechnologyObservation.collection_status == "SUCCESS",
        )
        .order_by(TechnologyObservation.observed_at, TechnologyObservation.effective_start)
    ).all()
    changes: list[dict[str, object]] = []
    prior: dict[uuid.UUID, TechnologyDetection] = {}
    for observation in observations:
        current = {
            row.technology_id: row
            for row in session.scalars(
                select(TechnologyDetection).where(
                    TechnologyDetection.observation_id == observation.id,
                    TechnologyDetection.presence_status == "PRESENT",
                )
            ).all()
        }
        for technology_id, detection in current.items():
            previous = prior.get(technology_id)
            change_type = (
                "ADDED"
                if previous is None
                else "VERSION_CHANGED"
                if previous.detected_version != detection.detected_version
                and detection.detected_version is not None
                else None
            )
            if change_type:
                technology = session.get(Technology, technology_id)
                changes.append(
                    {
                        "observed_at": observation.observed_at.isoformat(),
                        "technology": technology.slug if technology else str(technology_id),
                        "change_type": change_type,
                        "semantics": "GIS_DERIVED_COMPARABLE_PRESENT_OBSERVATIONS",
                    }
                )
        prior = current
    return changes
