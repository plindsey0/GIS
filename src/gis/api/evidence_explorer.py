"""Read-only, entity-centered evidence exploration."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.api.errors import ApiError
from gis.api.workbench import encoded
from gis.models import (
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    Domain,
    ExecutionAttempt,
    ExternalSearchObservation,
    IngestionRun,
    OrchestrationRun,
    RightsDecision,
    Technology,
    TechnologyAlias,
    TechnologyDetection,
    TechnologyEvidence,
    TechnologyObservation,
)


def source_options(session: Session) -> list[dict[str, str]]:
    return [
        {"value": row.key, "label": row.name, "provider": row.provider}
        for row in session.scalars(select(DataSource).order_by(DataSource.name))
    ]


def technology_domain_inventory(
    session: Session,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    *,
    page: int,
    limit: int,
    search: Optional[str] = None,
) -> dict[str, Any]:
    filters = [
        Domain.tenant_id == tenant_id,
        Domain.site_id == site_id,
        DataSource.key == "builtwith",
    ]
    if search:
        filters.append(Domain.hostname.ilike(f"%{search}%"))
    base = (
        select(Domain, func.max(TechnologyObservation.observed_at).label("fresh"))
        .join(TechnologyObservation, TechnologyObservation.domain == Domain.hostname)
        .join(
            DataSourceConnection,
            DataSourceConnection.id == TechnologyObservation.data_source_connection_id,
        )
        .join(DataSource, DataSource.id == DataSourceConnection.data_source_id)
        .where(*filters)
        .group_by(Domain.id)
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(
        base.order_by(func.max(TechnologyObservation.observed_at).desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    items = []
    for domain, fresh in rows:
        count = (
            session.scalar(
                select(func.count())
                .select_from(TechnologyDetection)
                .join(TechnologyObservation)
                .join(DataSourceConnection)
                .join(DataSource)
                .where(
                    TechnologyObservation.tenant_id == tenant_id,
                    TechnologyObservation.site_id == site_id,
                    TechnologyObservation.domain == domain.hostname,
                    DataSource.key == "builtwith",
                    TechnologyObservation.observed_at == fresh,
                )
            )
            or 0
        )
        items.append(
            {
                "id": f"domain-{domain.id}",
                "label": domain.hostname,
                "canonical_key": domain.hostname,
                "entity_type": "DOMAIN",
                "evidence_type": "TECHNOLOGY_PROFILE",
                "classification": "PROVIDER_REPORTED_HISTORY",
                "status": "OBSERVED",
                "sources": ["builtwith"],
                "source_count": 1,
                "gap_count": 0,
                "fresh_through": encoded(fresh),
                "technology_count": count,
                "href": f"/evidence/domains/{domain.id}",
            }
        )
    return {"items": items, "page": page, "limit": limit, "total": total}


def _domain(
    session: Session, domain_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> Domain:
    domain = session.scalar(
        select(Domain).where(
            Domain.id == domain_id, Domain.tenant_id == tenant_id, Domain.site_id == site_id
        )
    )
    if not domain:
        raise ApiError(404, "DOMAIN_NOT_FOUND", "Domain evidence subject not found in site scope.")
    return domain


def _orchestration_run(session: Session, ingestion_id: uuid.UUID) -> OrchestrationRun | None:
    run = session.scalar(
        select(OrchestrationRun).where(OrchestrationRun.ingestion_run_id == ingestion_id)
    )
    if run:
        return run
    return session.scalar(
        select(OrchestrationRun)
        .join(ExecutionAttempt)
        .where(ExecutionAttempt.ingestion_run_id == ingestion_id)
        .order_by(ExecutionAttempt.attempt_number.desc())
    )


def _headers(observation: TechnologyObservation, ingestion: IngestionRun) -> dict[str, Any]:
    values = ingestion.source_metadata.get("response_headers", {})
    if not isinstance(values, dict):
        values = observation.collection_metadata.get("response_headers", {})
    return values if isinstance(values, dict) else {}


def domain_evidence_detail(
    session: Session, domain_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> dict[str, Any]:
    domain = _domain(session, domain_id, tenant_id, site_id)
    observations = list(
        session.scalars(
            select(TechnologyObservation)
            .join(DataSourceConnection)
            .join(DataSource)
            .where(
                TechnologyObservation.tenant_id == tenant_id,
                TechnologyObservation.site_id == site_id,
                TechnologyObservation.domain == domain.hostname,
                DataSource.key == "builtwith",
            )
            .order_by(TechnologyObservation.observed_at.desc())
        )
    )
    latest = observations[0] if observations else None
    detections: list[dict[str, Any]] = []
    categories: Counter[str] = Counter()
    ingestion = session.get(IngestionRun, latest.ingestion_run_id) if latest else None
    orchestration = _orchestration_run(session, latest.ingestion_run_id) if latest else None
    if latest:
        rows = session.execute(
            select(TechnologyDetection, Technology)
            .join(Technology)
            .where(TechnologyDetection.observation_id == latest.id)
            .order_by(TechnologyDetection.provider_category, Technology.name)
        ).all()
        identifiers = {
            row.technology_id: row.provider_identifier
            for row in session.scalars(
                select(TechnologyAlias).where(
                    TechnologyAlias.source_key == "builtwith",
                    TechnologyAlias.technology_id.in_([tech.id for _, tech in rows]),
                )
            )
        }
        for detection, technology in rows:
            category = detection.provider_category or technology.category or "Unknown"
            categories[category] += 1
            detections.append(
                {
                    "id": str(detection.id),
                    "technology_name": technology.name,
                    "provider_technology_id": identifiers.get(technology.id),
                    "category": category,
                    "first_seen": encoded(detection.provider_first_seen_at),
                    "last_seen": encoded(detection.provider_last_seen_at),
                    "status": "PROVIDER_REPORTED_HISTORY",
                    "current_presence": "UNKNOWN",
                    "source": "BuiltWith",
                    "collected_at": encoded(latest.collected_at),
                    "href": f"/evidence/technology/{detection.id}",
                }
            )
    external = (
        session.scalar(
            select(func.count())
            .select_from(ExternalSearchObservation)
            .where(
                ExternalSearchObservation.tenant_id == tenant_id,
                ExternalSearchObservation.site_id == site_id,
                ExternalSearchObservation.target_domain == domain.hostname,
            )
        )
        or 0
    )
    headers = _headers(latest, ingestion) if latest and ingestion else {}
    duplicate_count = (ingestion.records_received - ingestion.records_inserted) if ingestion else 0
    consolidated_names: list[str] = []
    if latest and duplicate_count:
        consolidated_names = list(
            session.scalars(
                select(Technology.name)
                .join(TechnologyDetection)
                .join(TechnologyEvidence)
                .where(TechnologyDetection.observation_id == latest.id)
                .group_by(Technology.name, TechnologyDetection.id)
                .having(func.count(TechnologyEvidence.id) > 1)
                .order_by(Technology.name)
            )
        )
    consolidated_label = ", ".join(consolidated_names) or "a canonical technology"
    return {
        "id": str(domain.id),
        "label": domain.hostname,
        "description": "Canonical domain intelligence assembled from governed provider observations.",
        "summary": {
            "entity_type": "DOMAIN",
            "canonical_subject": domain.hostname,
            "domain_type": domain.domain_type.value,
            "primary_domain": domain.is_primary,
            "sources": [
                name
                for name, present in (
                    ("BuiltWith", bool(observations)),
                    ("DataForSEO / external search", external > 0),
                )
                if present
            ],
        },
        "facets": {
            "technology_profile": {
                "source": "BuiltWith",
                "observation_count": len(observations),
                "technology_count": len(detections),
                "collected_at": encoded(latest.collected_at) if latest else None,
                "temporal_semantics": "Provider-reported detection history; current presence is unknown.",
            },
            "search_domain_intelligence": {
                "observation_count": external,
                "status": "AVAILABLE" if external else "NO_MATCHING_OBSERVATIONS",
            },
        },
        "technology_profile": {
            "groups": [
                {"category": key, "count": value} for key, value in sorted(categories.items())
            ],
            "detections": detections,
        },
        "collection_accounting": {
            "records_received": ingestion.records_received if ingestion else None,
            "normalized_detections_inserted": ingestion.records_inserted if ingestion else None,
            "records_rejected": ingestion.records_rejected if ingestion else None,
            "explanation": (
                f"BuiltWith returned {ingestion.records_received} technology entries. GIS resolved them to "
                f"{ingestion.records_inserted} unique canonical technologies; {duplicate_count} repeated entry "
                f"for {consolidated_label} was consolidated into one technology detection while both "
                "distinct source signatures were preserved as provenance evidence. No records were rejected."
                if ingestion and duplicate_count == 1
                else "Received entries and unique normalized technology detections are counted separately."
            ),
        },
        "cost_and_credits": {
            "provider_requests": latest.request_count if latest else None,
            "provider_reported_credits_consumed": headers.get("x-api-credits-used"),
            "provider_reported_credits_remaining": headers.get("x-api-credits-remaining"),
            "provider_reported_credits_available": headers.get("x-api-credits-available"),
            "estimated_economic_cost": (
                str(latest.estimated_cost) if latest and latest.estimated_cost is not None else None
            ),
            "estimated_cost_currency": latest.cost_currency if latest else None,
            "actual_provider_usd_charge": (
                str(latest.provider_reported_cost)
                if latest and latest.provider_reported_cost is not None
                else None
            ),
            "actual_cost_semantics": "NOT_REPORTED"
            if latest and latest.provider_reported_cost is None
            else "PROVIDER_REPORTED",
        },
        "provenance": {
            "source": "/system/sources/builtwith" if latest else None,
            "observation_id": str(latest.id) if latest else None,
            "ingestion_run_id": str(latest.ingestion_run_id) if latest else None,
            "orchestration_run": f"/system/runs/{orchestration.id}" if orchestration else None,
            "rights_policy_id": str(latest.rights_policy_id) if latest else None,
            "rights_policy_version": latest.rights_policy_version if latest else None,
            "acquisition_method": encoded(ingestion.acquisition_method) if ingestion else None,
            "payload_hash": latest.content_hash if latest else None,
            "schema_version": ingestion.schema_version if ingestion else None,
        },
        "limitations": [
            "Provider history is not proof that a technology is currently installed.",
            "Actual provider USD charge was not reported; the configured value is an estimate.",
        ],
    }


def technology_detection_detail(
    session: Session, detection_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> dict[str, Any]:
    row = session.execute(
        select(TechnologyDetection, TechnologyObservation, Technology, DataSource, IngestionRun)
        .join(TechnologyObservation, TechnologyObservation.id == TechnologyDetection.observation_id)
        .join(Technology, Technology.id == TechnologyDetection.technology_id)
        .join(
            DataSourceConnection,
            DataSourceConnection.id == TechnologyObservation.data_source_connection_id,
        )
        .join(DataSource, DataSource.id == DataSourceConnection.data_source_id)
        .join(IngestionRun, IngestionRun.id == TechnologyObservation.ingestion_run_id)
        .where(
            TechnologyDetection.id == detection_id,
            TechnologyObservation.tenant_id == tenant_id,
            TechnologyObservation.site_id == site_id,
        )
    ).one_or_none()
    if not row:
        raise ApiError(
            404, "TECHNOLOGY_DETECTION_NOT_FOUND", "Technology evidence not found in site scope."
        )
    detection, observation, technology, source, ingestion = row
    policy = session.get(DataRightsPolicy, observation.rights_policy_id)
    raw_allowed = bool(policy and policy.raw_display_allowed is RightsDecision.ALLOWED)
    evidence = list(
        session.scalars(
            select(TechnologyEvidence).where(TechnologyEvidence.detection_id == detection.id)
        )
    )
    orchestration = _orchestration_run(session, ingestion.id)
    alias = session.scalar(
        select(TechnologyAlias).where(
            TechnologyAlias.technology_id == technology.id, TechnologyAlias.source_key == source.key
        )
    )
    result: dict[str, Any] = {
        "id": str(detection.id),
        "label": technology.name,
        "description": "A normalized technology detection backed by provider-reported historical evidence.",
        "technology": {
            "name": technology.name,
            "provider_technology_id": alias.provider_identifier if alias else None,
            "normalized_category": technology.category,
            "provider_category": detection.provider_category,
            "first_seen": encoded(detection.provider_first_seen_at),
            "last_seen": encoded(detection.provider_last_seen_at),
            "detection_semantics": detection.semantic_class,
            "current_presence": "UNKNOWN",
        },
        "observation": {
            "observation_id": str(observation.id),
            "target_domain": observation.domain,
            "collected_at": encoded(observation.collected_at),
            "source": source.name,
            "collection_status": observation.collection_status,
        },
        "evidence": [
            {
                "evidence_id": str(item.id),
                "type": item.evidence_type,
                "signature": item.signature_key,
                "schema_version": item.signature_version,
                "payload_hash": item.evidence_hash,
            }
            for item in evidence
        ],
        "provenance": {
            "domain": next(
                (
                    f"/evidence/domains/{item.id}"
                    for item in session.scalars(
                        select(Domain).where(
                            Domain.tenant_id == tenant_id,
                            Domain.site_id == site_id,
                            Domain.hostname == observation.domain,
                        )
                    )
                ),
                None,
            ),
            "ingestion_run_id": str(ingestion.id),
            "orchestration_run": f"/system/runs/{orchestration.id}" if orchestration else None,
            "source": f"/system/sources/{source.key}",
            "rights_policy_id": str(observation.rights_policy_id),
            "rights_policy_version": observation.rights_policy_version,
            "acquisition_method": ingestion.acquisition_method.value,
            "payload_hash": observation.content_hash,
            "schema_version": ingestion.schema_version,
        },
        "raw_display": {
            "status": "ALLOWED" if raw_allowed else "WITHHELD",
            "reason": "Raw evidence is shown only when the recorded policy explicitly allows raw display.",
        },
    }
    if raw_allowed:
        result["raw_provider_evidence"] = [
            json.loads(item.evidence_value) for item in evidence if item.evidence_value
        ]
    return result
