"""Evidence-driven recovery for the 2026-09-04 local provider-control incident."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.db import make_engine
from gis.models import (
    DataSource,
    DataSourceConnection,
    Domain,
    PermittedUse,
    PipelineDefinition,
    ProviderCapability,
    ProviderCapabilityPolicy,
    ProviderCollectionPolicy,
    ProviderCollectionTarget,
    ProviderControlRecoveryIncident,
    ProviderDefinition,
    ProviderPolicyAuditEvent,
    ProviderPricingConfiguration,
    RightsStatus,
    ScheduleDefinition,
    ScheduledTarget,
    TrackedQuery,
)
from gis.provenance.service import evaluate_connection_use

INCIDENT_KEY = "2026-09-04-provider-control-data-loss"
CLASSIFICATION = "LOCAL_DEV_MIGRATION_TEST_PROVIDER_CONTROL_DATA_LOSS"
DOCUMENTATION = "docs/gis/recovery/2026-09-04-provider-control-recovery.md"
AFFECTED_TABLES = [
    "provider_account_telemetry",
    "provider_capability",
    "provider_capability_policy",
    "provider_collection_policy",
    "provider_collection_target",
    "provider_definition",
    "provider_policy_audit_event",
    "provider_pricing_configuration",
    "provider_usage_event",
]
ROW_COUNTS = {
    "provider_account_telemetry": {"before": 2, "after_incident": 0},
    "provider_capability": {"before": 9, "after_incident": 9},
    "provider_capability_policy": {"before": 7, "after_incident": 4},
    "provider_collection_policy": {"before": 5, "after_incident": 3},
    "provider_collection_target": {"before": 3, "after_incident": 0},
    "provider_definition": {"before": 7, "after_incident": 7},
    "provider_policy_audit_event": {"before": 51, "after_incident": 0},
    "provider_pricing_configuration": {"before": 13, "after_incident": 0},
    "provider_usage_event": {"before": 6, "after_incident": 0},
}
HISTORY_COMPLETENESS = {
    "provider_usage": "PARTIAL",
    "provider_policy_audit": "PARTIAL",
    "provider_account_telemetry": "PARTIAL",
    "provider_pricing": "PARTIAL",
    "provider_target_lifecycle": "PARTIAL",
}


def _provider(session: Session, key: str) -> ProviderDefinition:
    row = session.scalar(select(ProviderDefinition).where(ProviderDefinition.provider_key == key))
    if row is None:
        raise RuntimeError(f"Required provider is missing: {key}")
    return row


def _connection(session: Session, key: str) -> DataSourceConnection:
    row = session.scalar(
        select(DataSourceConnection)
        .join(DataSource)
        .where(DataSource.key == key, DataSourceConnection.status == "ACTIVE")
        .order_by(DataSourceConnection.created_at.desc())
    )
    if row is None or not row.credential_reference:
        raise RuntimeError(f"Surviving active credential reference is missing: {key}")
    return row


def _capability(session: Session, provider_id: uuid.UUID, key: str) -> ProviderCapability:
    row = session.scalar(
        select(ProviderCapability).where(
            ProviderCapability.provider_id == provider_id,
            ProviderCapability.capability_key == key,
        )
    )
    if row is None:
        raise RuntimeError(f"Required capability is missing: {key}")
    return row


def _targets(session: Session, connection: DataSourceConnection) -> tuple[TrackedQuery, Domain]:
    query = session.scalar(
        select(TrackedQuery).where(
            TrackedQuery.tenant_id == connection.tenant_id,
            TrackedQuery.site_id == connection.site_id,
            TrackedQuery.normalized_query == "va loan calculator",
        )
    )
    domain = session.scalar(
        select(Domain).where(
            Domain.tenant_id == connection.tenant_id,
            Domain.site_id == connection.site_id,
            Domain.hostname == "vahomemath.com",
        )
    )
    if query is None or domain is None:
        raise RuntimeError("Surviving canonical recovery targets are missing")
    return query, domain


def recovery_plan(session: Session) -> dict[str, Any]:
    _provider(session, "dataforseo")
    _provider(session, "builtwith")
    dfs_connection = _connection(session, "dataforseo")
    bw_connection = _connection(session, "builtwith")
    if (
        dfs_connection.tenant_id != bw_connection.tenant_id
        or dfs_connection.site_id != bw_connection.site_id
    ):
        raise RuntimeError("Provider connections do not share the expected tenant/site scope")
    query, domain = _targets(session, dfs_connection)
    if bw_connection.rights_policy_id is None:
        raise RuntimeError("BuiltWith surviving reviewed rights policy is missing")
    for permitted_use in (
        PermittedUse.RAW_RETENTION,
        PermittedUse.NORMALIZED_RETENTION,
        PermittedUse.INTERNAL_ANALYSIS,
    ):
        if (
            evaluate_connection_use(session, bw_connection, permitted_use).status
            != RightsStatus.ALLOWED
        ):
            raise RuntimeError(f"BuiltWith recovery rights are not ALLOWED: {permitted_use.value}")
    return {
        "incident_key": INCIDENT_KEY,
        "mode": "DRY_RUN",
        "dataforseo": {
            "collection_policy": "CREATE_NEW",
            "connection": "REUSE_SURVIVING",
            "capabilities": [
                {
                    "key": "SERP_COLLECTION",
                    "state": "ENABLED",
                    "target": query.normalized_query,
                    "cadence": "WEEKLY_FRIDAY_0700_AMERICA_NEW_YORK",
                    "pricing": "0.018 USD reconstructed estimate from surviving run evidence",
                },
                {
                    "key": "DOMAIN_SEARCH_INTELLIGENCE",
                    "state": "ENABLED",
                    "target": domain.hostname,
                    "cadence": "MANUAL_ONLY",
                    "search_market": {"location_code": 2840, "language_code": "en"},
                    "pricing": "0.0132 USD reconstructed estimate from surviving run evidence",
                },
            ],
            "budgets": {"monthly_soft": "20", "monthly_hard": "30", "per_run_hard": "5"},
            "request_limits": {"daily": 20, "monthly": 100, "per_run": 1},
            "schedule": "REASSOCIATE_EXISTING; CREATE_OBLIGATIONS=0",
            "evidence": "surviving connection, schedule, runs, attempts, ingestion and committed validation",
            "status": "RECONSTRUCTED_CURRENT_STATE",
        },
        "builtwith": {
            "collection_policy": "CREATE_NEW",
            "connection": "REUSE_SURVIVING",
            "rights_policy": str(bw_connection.rights_policy_id),
            "capability": "TECHNOLOGY_PROFILE",
            "state": "ENABLED",
            "target": domain.hostname,
            "cadence": "MANUAL_ONLY",
            "budgets": {
                "daily_soft": "0.10",
                "daily_hard": "0.25",
                "monthly_soft": "1.00",
                "monthly_hard": "2.50",
                "per_run_hard": "0.10",
            },
            "request_limits": {"daily": 1, "monthly": 5, "per_run": 1},
            "pricing": "0.0495 USD estimated acquisition-cost basis; not actual provider charge",
            "account_telemetry": "UNKNOWN_NOT_REFRESHED",
            "schedule": "REASSOCIATE_EXISTING_DISABLED; CREATE_OBLIGATIONS=0",
            "evidence": "surviving connection, reviewed rights, run, attempt, ingestion, evidence and operator record",
            "status": "RECONSTRUCTED_CURRENT_STATE",
        },
        "expected_new_rows": {
            "provider_control_recovery_incident": 1,
            "provider_collection_policy": 2,
            "provider_capability_policy": 3,
            "provider_collection_target": 3,
            "provider_pricing_configuration": 3,
            "provider_policy_audit_event": 11,
        },
        "historical_records_recreated": 0,
        "lost_usage_events_recreated": 0,
        "lost_telemetry_snapshots_recreated": 0,
        "lost_audit_events_recreated": 0,
        "paid_provider_calls": 0,
    }


def _audit(
    session: Session,
    incident: ProviderControlRecoveryIncident,
    policy: ProviderCollectionPolicy,
    action: str,
    now: datetime,
    after: dict[str, Any],
) -> None:
    session.add(
        ProviderPolicyAuditEvent(
            tenant_id=policy.tenant_id,
            site_id=policy.site_id,
            provider_id=policy.provider_id,
            collection_policy_id=policy.id,
            recovery_incident_id=incident.id,
            action=action,
            actor="codex-recovery",
            reason=f"Current state established after {INCIDENT_KEY}; not historical restoration",
            before_json={},
            after_json=after,
            occurred_at=now,
        )
    )


def _policy(
    session: Session,
    provider: ProviderDefinition,
    connection: DataSourceConnection,
    now: datetime,
    **values: Any,
) -> ProviderCollectionPolicy:
    existing = session.scalar(
        select(ProviderCollectionPolicy).where(
            ProviderCollectionPolicy.tenant_id == connection.tenant_id,
            ProviderCollectionPolicy.site_id == connection.site_id,
            ProviderCollectionPolicy.provider_id == provider.id,
        )
    )
    if existing is not None:
        raise RuntimeError(
            f"Recovery refuses to replace an existing {provider.provider_key} policy"
        )
    policy = ProviderCollectionPolicy(
        tenant_id=connection.tenant_id,
        site_id=connection.site_id,
        provider_id=provider.id,
        data_source_connection_id=connection.id,
        master_enabled=True,
        status="ACTIVE",
        currency="USD",
        timezone="America/New_York",
        effective_start_at=now,
        created_by="codex-recovery",
        updated_by="codex-recovery",
        **values,
    )
    session.add(policy)
    session.flush()
    return policy


def _capability_policy(
    session: Session,
    policy: ProviderCollectionPolicy,
    capability: ProviderCapability,
    cadence: str,
    schedule_configuration: dict[str, Any],
) -> ProviderCapabilityPolicy:
    row = ProviderCapabilityPolicy(
        collection_policy_id=policy.id,
        capability_id=capability.id,
        enabled=True,
        cadence=cadence,
        schedule_configuration_json=schedule_configuration,
        freshness_target_seconds=604800 if cadence == "WEEKLY" else 2592000,
        priority="STANDARD",
        per_run_limit=1,
        configuration_json={"recovery_incident": INCIDENT_KEY},
    )
    session.add(row)
    session.flush()
    return row


def _target(
    session: Session,
    capability_policy: ProviderCapabilityPolicy,
    kind: str,
    reference_id: uuid.UUID,
    value: str,
    now: datetime,
) -> ProviderCollectionTarget:
    row = ProviderCollectionTarget(
        capability_policy_id=capability_policy.id,
        target_type=kind,
        target_reference_id=reference_id,
        target_value=value,
        enabled=True,
        priority="STANDARD",
        metadata_json={
            "authorization_basis": "RECOVERY_SURVIVING_EVIDENCE",
            "effective_from": now.isoformat(),
            "recovery_incident": INCIDENT_KEY,
        },
    )
    session.add(row)
    session.flush()
    return row


def _price(
    session: Session,
    provider: ProviderDefinition,
    capability: ProviderCapability,
    connection: DataSourceConnection,
    amount: str,
    notes: str,
    now: datetime,
) -> ProviderPricingConfiguration:
    row = ProviderPricingConfiguration(
        tenant_id=connection.tenant_id,
        site_id=connection.site_id,
        provider_id=provider.id,
        capability_id=capability.id,
        pricing_model="PER_REQUEST",
        unit_price=Decimal(amount),
        units_per_price=Decimal(1),
        currency="USD",
        provenance="RECOVERY_DOCUMENTED_BASIS",
        effective_start_at=now,
        last_verified_at=now,
        notes=notes,
    )
    session.add(row)
    session.flush()
    return row


def _reassociate_schedule(
    session: Session,
    connection: DataSourceConnection,
    pipeline_key: str,
    capability_policy: ProviderCapabilityPolicy,
    target: ProviderCollectionTarget,
) -> None:
    schedule = session.scalar(
        select(ScheduleDefinition)
        .join(PipelineDefinition)
        .where(
            ScheduleDefinition.data_source_connection_id == connection.id,
            PipelineDefinition.key == pipeline_key,
        )
    )
    if schedule is None:
        raise RuntimeError(f"Surviving schedule is missing: {pipeline_key}")
    configuration = dict(schedule.configuration_json or {})
    configuration["provider_capability_policy_id"] = str(capability_policy.id)
    configuration["provider_policy_version"] = str(capability_policy.collection_policy_id)
    configuration["recovery_incident"] = INCIDENT_KEY
    schedule.configuration_json = configuration
    scheduled_target = session.scalar(
        select(ScheduledTarget).where(ScheduledTarget.schedule_id == schedule.id)
    )
    if scheduled_target is None:
        raise RuntimeError(f"Surviving scheduled target is missing: {pipeline_key}")
    scheduled_target.target_key = str(target.id)


def apply_recovery(session: Session, backup_path: str, git_sha: str) -> dict[str, Any]:
    archive = Path(backup_path).expanduser()
    if not archive.is_file() or archive.stat().st_size <= 0:
        raise RuntimeError("Verified pre-recovery backup is required")
    existing = session.scalar(
        select(ProviderControlRecoveryIncident).where(
            ProviderControlRecoveryIncident.incident_key == INCIDENT_KEY
        )
    )
    if existing is not None:
        return {"status": "ALREADY_COMPLETE", "incident_id": str(existing.id), "paid_calls": 0}
    plan = recovery_plan(session)
    now = datetime.now(timezone.utc)
    incident = ProviderControlRecoveryIncident(
        incident_key=INCIDENT_KEY,
        classification=CLASSIFICATION,
        environment="local_development",
        status="RECOVERING",
        occurred_at=datetime(2026, 9, 4, 22, 39, 32, tzinfo=timezone.utc),
        detected_at=now,
        recovery_started_at=now,
        actor="codex-recovery",
        affected_tables=AFFECTED_TABLES,
        row_counts=ROW_COUNTS,
        history_completeness={**HISTORY_COMPLETENESS, "complete_since": now.isoformat()},
        exact_restoration_available=False,
        historical_rows_recreated=0,
        backup_path=str(archive),
        documentation_reference=DOCUMENTATION,
        git_branch="codex/epic-26a-opportunity-collection-sufficiency",
        git_sha=git_sha,
        notes="Operational current state reconstructed; pre-incident provider-control history remains incomplete.",
    )
    session.add(incident)
    session.flush()

    dfs = _provider(session, "dataforseo")
    bw = _provider(session, "builtwith")
    dfs_connection = _connection(session, "dataforseo")
    bw_connection = _connection(session, "builtwith")
    query, domain = _targets(session, dfs_connection)

    dfs_policy = _policy(
        session,
        dfs,
        dfs_connection,
        now,
        monthly_soft_budget=Decimal("20"),
        monthly_hard_budget=Decimal("30"),
        per_run_hard_budget=Decimal("5"),
        daily_request_limit=20,
        monthly_request_limit=100,
        per_run_request_limit=1,
        allow_unknown_cost=False,
    )
    bw_policy = _policy(
        session,
        bw,
        bw_connection,
        now,
        daily_soft_budget=Decimal("0.10"),
        daily_hard_budget=Decimal("0.25"),
        monthly_soft_budget=Decimal("1.00"),
        monthly_hard_budget=Decimal("2.50"),
        per_run_hard_budget=Decimal("0.10"),
        daily_request_limit=1,
        monthly_request_limit=5,
        per_run_request_limit=1,
        allow_unknown_cost=False,
    )
    _audit(
        session,
        incident,
        dfs_policy,
        "RECOVERY_COLLECTION_POLICY_ESTABLISHED",
        now,
        plan["dataforseo"]["budgets"],
    )
    _audit(
        session,
        incident,
        bw_policy,
        "RECOVERY_COLLECTION_POLICY_ESTABLISHED",
        now,
        plan["builtwith"]["budgets"],
    )

    serp_cap = _capability(session, dfs.id, "SERP_COLLECTION")
    domain_cap = _capability(session, dfs.id, "DOMAIN_SEARCH_INTELLIGENCE")
    bw_cap = _capability(session, bw.id, "TECHNOLOGY_PROFILE")
    serp_cp = _capability_policy(
        session, dfs_policy, serp_cap, "WEEKLY", {"hour": 7, "minute": 0, "weekday": 5}
    )
    domain_cp = _capability_policy(
        session,
        dfs_policy,
        domain_cap,
        "MANUAL_ONLY",
        {"location_code": 2840, "language_code": "en", "hour": 8, "minute": 0},
    )
    bw_cp = _capability_policy(session, bw_policy, bw_cap, "MANUAL_ONLY", {"hour": 8, "minute": 0})
    for policy, cp, key in (
        (dfs_policy, serp_cp, "SERP_COLLECTION"),
        (dfs_policy, domain_cp, "DOMAIN_SEARCH_INTELLIGENCE"),
        (bw_policy, bw_cp, "TECHNOLOGY_PROFILE"),
    ):
        _audit(
            session,
            incident,
            policy,
            "RECOVERY_CAPABILITY_POLICY_ESTABLISHED",
            now,
            {"capability": key, "cadence": cp.cadence},
        )

    serp_target = _target(session, serp_cp, "QUERY", query.id, query.normalized_query, now)
    domain_target = _target(session, domain_cp, "DOMAIN", domain.id, domain.hostname, now)
    bw_target = _target(session, bw_cp, "DOMAIN", domain.id, domain.hostname, now)
    for policy, target, key in (
        (dfs_policy, serp_target, "SERP_COLLECTION"),
        (dfs_policy, domain_target, "DOMAIN_SEARCH_INTELLIGENCE"),
        (bw_policy, bw_target, "TECHNOLOGY_PROFILE"),
    ):
        _audit(
            session,
            incident,
            policy,
            "RECOVERY_TARGET_AUTHORIZED",
            now,
            {"capability": key, "target": target.target_value},
        )

    prices = (
        (
            dfs_policy,
            dfs,
            serp_cap,
            dfs_connection,
            "0.018",
            "Re-established after local recovery from surviving real SERP run cost evidence; current estimate only, not reconstructed ledger history.",
        ),
        (
            dfs_policy,
            dfs,
            domain_cap,
            dfs_connection,
            "0.0132",
            "Re-established after local recovery from surviving real Domain Search run cost evidence; current estimate only, not reconstructed ledger history.",
        ),
        (
            bw_policy,
            bw,
            bw_cap,
            bw_connection,
            "0.0495",
            "Re-established after local recovery using the operator-documented $99/2,000-credit acquisition basis; estimated economic cost, not provider-reported actual USD charge.",
        ),
    )
    for policy, provider, cap, connection, amount, notes in prices:
        _price(session, provider, cap, connection, amount, notes, now)
        _audit(
            session,
            incident,
            policy,
            "RECOVERY_PRICING_CONFIGURATION_ESTABLISHED",
            now,
            {
                "capability": cap.capability_key,
                "unit_price": amount,
                "semantics": "RECONSTRUCTED_CURRENT_ESTIMATE",
            },
        )

    _reassociate_schedule(session, dfs_connection, "serp", serp_cp, serp_target)
    _reassociate_schedule(session, dfs_connection, "external_search", domain_cp, domain_target)
    _reassociate_schedule(session, bw_connection, "builtwith_technology", bw_cp, bw_target)
    incident.status = "COMPLETED"
    incident.recovery_completed_at = datetime.now(timezone.utc)
    session.flush()
    return {
        "status": "COMPLETED",
        "incident_id": str(incident.id),
        "new_rows": plan["expected_new_rows"],
        "historical_rows_recreated": 0,
        "paid_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="2026-09-04 provider-control recovery")
    parser.add_argument("--apply", action="store_true", help="Apply the incident-specific plan")
    parser.add_argument("--backup-path")
    parser.add_argument("--git-sha", default="0c5b314e48328d35a384980b7bb439473f034903")
    args = parser.parse_args()
    engine = make_engine()
    with Session(engine) as session:
        if not args.apply:
            print(json.dumps(recovery_plan(session), indent=2, default=str))
            return
        if os.environ.get("GIS_ENVIRONMENT") not in {"development", "local_development"}:
            raise SystemExit("Recovery apply requires GIS_ENVIRONMENT=local_development")
        if not args.backup_path:
            raise SystemExit("Recovery apply requires --backup-path")
        result = apply_recovery(session, args.backup_path, args.git_sha)
        session.commit()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
