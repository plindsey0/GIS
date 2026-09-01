from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from gis.models import (
    CalculatorRun,
    CompetitiveContentObservation,
    ConnectionStatus,
    Conversion,
    DataRightsGrant,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    ExperienceObservation,
    ExternalSearchObservation,
    GA4AcquisitionObservation,
    GA4EventObservation,
    GA4LandingPageObservation,
    GSCSearchObservation,
    IngestionRun,
    PermittedUse,
    PipelineDefinition,
    ProductEvent,
    ProductSession,
    RightsDecision,
    RightsStatus,
    ScheduleDefinition,
    ScheduleStatus,
    SerpObservation,
    TechnologyObservation,
)
from gis.orchestration.schedule import next_occurrence

POLICY_VERSION = "operator-review-2026-09-01"


@dataclass(frozen=True)
class ReviewedPolicy:
    name: str
    source_keys: tuple[str, ...]
    allowed: frozenset[PermittedUse]
    denied: frozenset[PermittedUse]
    notes: str


PRIVATE_ANALYTICS_ALLOWED = frozenset(
    {
        PermittedUse.INTERNAL_ANALYSIS,
        PermittedUse.RAW_RETENTION,
        PermittedUse.NORMALIZED_RETENTION,
        PermittedUse.DERIVATIVE_CREATION,
        PermittedUse.AGGREGATE_STATISTICS,
        PermittedUse.CUSTOMER_FACING_DISPLAY,
    }
)
PRIVATE_ANALYTICS_DENIED = frozenset(
    {
        PermittedUse.EXTERNAL_PUBLICATION,
        PermittedUse.RAW_REDISTRIBUTION,
        PermittedUse.NORMALIZED_REDISTRIBUTION,
        PermittedUse.CUSTOMER_EXPORT,
        PermittedUse.RAG_RETRIEVAL,
        PermittedUse.AI_TRAINING,
    }
)

REVIEWED_POLICIES = (
    ReviewedPolicy(
        "GSC first-party reviewed rights",
        ("google_search_console",),
        PRIVATE_ANALYTICS_ALLOWED,
        PRIVATE_ANALYTICS_DENIED,
        "Operator-approved first-party GSC storage, deterministic analysis, derivatives, aggregation, evidence, signals, and private GIS display.",
    ),
    ReviewedPolicy(
        "GA4 first-party reviewed rights",
        ("ga4",),
        PRIVATE_ANALYTICS_ALLOWED,
        PRIVATE_ANALYTICS_DENIED,
        "Operator-approved first-party GA4 storage, deterministic analysis, derivatives, aggregation, evidence, signals, and private GIS display.",
    ),
    ReviewedPolicy(
        "First-party telemetry reviewed rights",
        ("first_party",),
        PRIVATE_ANALYTICS_ALLOWED,
        PRIVATE_ANALYTICS_DENIED,
        "Operator-approved private first-party telemetry analytics; personal identity resolution and cross-tenant learning are not permitted.",
    ),
    ReviewedPolicy(
        "DataForSEO SERP and external-search reviewed rights",
        ("dataforseo",),
        PRIVATE_ANALYTICS_ALLOWED,
        PRIVATE_ANALYTICS_DENIED,
        "Operator-approved licensed-provider storage and private summarized analytics. Underlying provider records remain non-redistributable; paid retrieval is controlled separately and remains disabled.",
    ),
    ReviewedPolicy(
        "Competitive content reviewed rights",
        ("direct_http",),
        PRIVATE_ANALYTICS_ALLOWED - {PermittedUse.RAW_RETENTION},
        PRIVATE_ANALYTICS_DENIED | {PermittedUse.RAW_RETENTION},
        "Operator-approved analysis of already-collected public competitive pages. Raw-body retention and redistribution remain prohibited.",
    ),
    ReviewedPolicy(
        "Competitive technology reviewed rights",
        ("direct_technology",),
        PRIVATE_ANALYTICS_ALLOWED - {PermittedUse.RAW_RETENTION},
        PRIVATE_ANALYTICS_DENIED | {PermittedUse.RAW_RETENTION},
        "Operator-approved analysis of already-collected public technology signals. Raw-body retention and redistribution remain prohibited.",
    ),
    ReviewedPolicy(
        "Google PageSpeed and CrUX public API reviewed rights",
        ("pagespeed", "crux"),
        PRIVATE_ANALYTICS_ALLOWED,
        PRIVATE_ANALYTICS_DENIED,
        "Operator-approved use of Google PageSpeed Insights and Chrome UX Report public API data for deterministic performance analysis, historical storage, derived metrics, evidence generation, aggregation, and private GIS display. Automated retrieval is permitted only while it remains validated zero-cost and within configured quota controls; this is an operational review, not a legal determination.",
    ),
)


def _decision(
    use: PermittedUse,
    allowed: frozenset[PermittedUse],
    denied: frozenset[PermittedUse],
) -> RightsStatus:
    if use in allowed:
        return RightsStatus.ALLOWED
    if use in denied:
        return RightsStatus.DENIED
    return RightsStatus.UNKNOWN


def _policy(session: Session, tenant_id: uuid.UUID, spec: ReviewedPolicy) -> DataRightsPolicy:
    row = session.scalar(
        select(DataRightsPolicy).where(
            DataRightsPolicy.tenant_id == tenant_id,
            DataRightsPolicy.name == spec.name,
            DataRightsPolicy.policy_version == POLICY_VERSION,
        )
    )
    if row:
        return row
    placeholder = session.scalar(
        select(DataRightsPolicy).where(
            DataRightsPolicy.tenant_id.is_(None),
            DataRightsPolicy.name == "Unreviewed source rights",
        )
    )
    effective = datetime.now(timezone.utc)
    row = DataRightsPolicy(
        tenant_id=tenant_id,
        name=spec.name,
        commercial_use_allowed=RightsDecision.UNKNOWN,
        third_party_processing_allowed=RightsDecision.UNKNOWN,
        deterministic_analysis_allowed=RightsDecision.ALLOWED,
        ai_inference_allowed=RightsDecision.UNKNOWN,
        model_training_allowed=RightsDecision.PROHIBITED,
        raw_storage_allowed=RightsDecision.ALLOWED,
        derived_storage_allowed=RightsDecision.ALLOWED,
        raw_display_allowed=RightsDecision.PROHIBITED,
        derived_display_allowed=RightsDecision.ALLOWED,
        aggregation_allowed=RightsDecision.ALLOWED,
        cross_tenant_learning_allowed=RightsDecision.PROHIBITED,
        attribution_required=RightsDecision.UNKNOWN,
        policy_notes=spec.notes,
        policy_version=POLICY_VERSION,
        effective_at=effective,
        reviewed_at=effective,
        review_authority="GIS operator",
        documented_basis="Explicit operator governance activation dated 2026-09-01.",
        supersedes_policy_id=placeholder.id if placeholder else None,
    )
    session.add(row)
    session.flush()
    for use in PermittedUse:
        status = _decision(use, spec.allowed, spec.denied)
        session.add(
            DataRightsGrant(
                policy_id=row.id,
                permitted_use=use,
                status=status,
                reason=f"Explicit operator review for {spec.name}; {use.value}={status.value}.",
            )
        )
    session.flush()
    return row


def activate_reviewed_policies(session: Session, tenant_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Activate explicit source policies and reclassify stored rows without deleting history."""
    policies: dict[str, DataRightsPolicy] = {}
    for spec in REVIEWED_POLICIES:
        policy = _policy(session, tenant_id, spec)
        for source_key in spec.source_keys:
            source = session.scalar(select(DataSource).where(DataSource.key == source_key))
            if not source:
                raise ValueError(f"required data source is not registered: {source_key}")
            source.default_rights_policy_id = policy.id
            session.execute(
                update(DataSourceConnection)
                .where(
                    DataSourceConnection.tenant_id == tenant_id,
                    DataSourceConnection.data_source_id == source.id,
                )
                .values(rights_policy_id=policy.id)
            )
            connection_ids = select(DataSourceConnection.id).where(
                DataSourceConnection.tenant_id == tenant_id,
                DataSourceConnection.data_source_id == source.id,
            )
            session.execute(
                update(IngestionRun)
                .where(
                    IngestionRun.tenant_id == tenant_id,
                    IngestionRun.data_source_connection_id.in_(connection_ids),
                )
                .values(rights_policy_id=policy.id)
            )
            policies[source_key] = policy

    scoped_updates = (
        (GSCSearchObservation, policies["google_search_console"]),
        (GA4LandingPageObservation, policies["ga4"]),
        (GA4AcquisitionObservation, policies["ga4"]),
        (GA4EventObservation, policies["ga4"]),
        (SerpObservation, policies["dataforseo"]),
        (ExternalSearchObservation, policies["dataforseo"]),
        (ProductSession, policies["first_party"]),
        (CalculatorRun, policies["first_party"]),
        (ProductEvent, policies["first_party"]),
        (Conversion, policies["first_party"]),
        (CompetitiveContentObservation, policies["direct_http"]),
        (TechnologyObservation, policies["direct_technology"]),
        (ExperienceObservation, policies["pagespeed"]),
    )
    for model, policy in scoped_updates:
        values: dict[str, object] = {"rights_policy_id": policy.id}
        if hasattr(model, "rights_policy_version"):
            values["rights_policy_version"] = policy.policy_version
        session.execute(update(model).where(model.tenant_id == tenant_id).values(**values))
    session.commit()
    return {key: policy.id for key, policy in policies.items()}


def activate_safe_schedules(
    session: Session,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    market_id: uuid.UUID,
    gsc_connection_id: uuid.UUID,
    ga4_connection_id: uuid.UUID,
    experience_connection_id: uuid.UUID | None = None,
    *,
    google_validated: bool,
    experience_validated: bool = False,
) -> dict[str, str]:
    """Enable only proven zero-cost schedules; paid/provider templates are untouched."""
    if not google_validated:
        raise ValueError("Google schedules require explicit successful validation")
    sources = {
        row.key: row
        for row in session.scalars(
            select(DataSource).where(
                DataSource.key.in_(
                    ("google_search_console", "ga4", "dataforseo", "pagespeed", "crux")
                )
            )
        )
    }
    connections = {
        "gsc": session.get(DataSourceConnection, gsc_connection_id),
        "ga4": session.get(DataSourceConnection, ga4_connection_id),
    }
    if experience_connection_id:
        connections["experience"] = session.get(DataSourceConnection, experience_connection_id)
    for key, source_key in (("gsc", "google_search_console"), ("ga4", "ga4")):
        connection = connections[key]
        source = sources.get(source_key)
        if (
            not connection
            or not source
            or connection.tenant_id != tenant_id
            or connection.site_id != site_id
            or connection.data_source_id != source.id
            or connection.status is not ConnectionStatus.ACTIVE
        ):
            raise ValueError(f"{key} connection is not active in the requested scope")
    if experience_connection_id:
        connection = connections["experience"]
        source = sources.get("pagespeed")
        if not experience_validated:
            raise ValueError("experience schedule requires explicit successful validation")
        if (
            not connection
            or not source
            or connection.tenant_id != tenant_id
            or connection.site_id != site_id
            or connection.data_source_id != source.id
            or connection.status is not ConnectionStatus.ACTIVE
            or connection.credential_reference != "env:GIS_PAGESPEED_API_KEY"
        ):
            raise ValueError("experience connection is not active in the requested scope")

    configured: dict[str, str] = {}
    schedules = session.scalars(
        select(ScheduleDefinition)
        .join(PipelineDefinition, PipelineDefinition.id == ScheduleDefinition.pipeline_id)
        .where(
            ScheduleDefinition.tenant_id == tenant_id,
            ScheduleDefinition.site_id == site_id,
            PipelineDefinition.key.in_(
                (
                    "gsc",
                    "ga4",
                    "market_intelligence",
                    *(("experience",) if experience_connection_id else ()),
                )
            ),
        )
    ).all()
    for schedule in schedules:
        pipeline = session.get(PipelineDefinition, schedule.pipeline_id)
        assert pipeline
        if pipeline.key in connections:
            connection = connections[pipeline.key]
            assert connection
            schedule.data_source_connection_id = connection.id
            schedule.rights_policy_id = connection.rights_policy_id
            arguments = ["sync", "--connection", str(connection.id)]
            if pipeline.key == "experience":
                arguments.extend(
                    [
                        "--target",
                        "https://www.vahomemath.com",
                        "--form-factor",
                        "MOBILE",
                        "--scope",
                        "URL",
                    ]
                )
            else:
                arguments.extend(["--recent-days", "7"])
            schedule.configuration_json = {
                "arguments": arguments,
                "actual_cost": "0",
                "timeout_seconds": 900,
                "requires_operator_configuration": False,
                "validation": (
                    "operator confirmed enabled APIs, zero-cost quota, restricted credentials, and successful live collection on 2026-09-01"
                    if pipeline.key == "experience"
                    else "read-only property access confirmed 2026-09-01"
                ),
            }
        else:
            policy_id = sources["dataforseo"].default_rights_policy_id
            if not policy_id:
                raise ValueError("market schedule requires reviewed stored-evidence rights")
            pipeline.handler_key = "LOCAL_PROCESSING"
            schedule.rights_policy_id = policy_id
            schedule.configuration_json = {
                "market_id": str(market_id),
                "rights_policy_id": str(policy_id),
                "actual_cost": "0",
                "requires_operator_configuration": False,
                "processing_mode": "stored_data_only",
            }
        schedule.status = ScheduleStatus.ENABLED
        schedule.next_scheduled_at = next_occurrence(
            schedule.cron_expression, schedule.timezone, datetime.now(timezone.utc)
        )
        configured[pipeline.key] = schedule.status.value
    expected = {"gsc", "ga4", "market_intelligence"}
    if experience_connection_id:
        expected.add("experience")
    if set(configured) != expected:
        raise ValueError("required safe schedule definitions are missing")
    session.commit()
    return configured
