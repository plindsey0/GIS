"""Derived orchestration bindings; provider policies remain the source of truth."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    DataSourceConnection,
    ObligationStatus,
    OrchestrationObligation,
    OrchestrationRun,
    OrchestrationStatus,
    PipelineDefinition,
    ProviderCapability,
    ProviderCapabilityPolicy,
    ProviderCollectionPolicy,
    ProviderCollectionTarget,
    ProviderDefinition,
    ScheduleDefinition,
    ScheduledTarget,
    ScheduleStatus,
)
from gis.orchestration.schedule import next_occurrence
from gis.provider_control.configuration import (
    BINDINGS,
    CapabilityConfiguration,
    ConfigurationService,
    cron,
)
from gis.provider_control.service import ProviderControlService


def reconcile_schedules(session: Session, policy: ProviderCollectionPolicy) -> None:
    provider = session.get(ProviderDefinition, policy.provider_id)
    assert provider is not None
    caps = session.scalars(
        select(ProviderCapability).where(ProviderCapability.provider_id == provider.id)
    ).all()
    cps = {
        cp.capability_id: cp
        for cp in session.scalars(
            select(ProviderCapabilityPolicy).where(
                ProviderCapabilityPolicy.collection_policy_id == policy.id
            )
        )
    }
    for pending_manual in session.scalars(
        select(OrchestrationRun).where(
            OrchestrationRun.tenant_id == policy.tenant_id,
            OrchestrationRun.site_id == policy.site_id,
            OrchestrationRun.schedule_id.is_(None),
            OrchestrationRun.configuration_json["provider_capability_policy_id"].astext.in_(
                [str(cp.id) for cp in cps.values()]
            ),
            OrchestrationRun.status.in_(
                [
                    OrchestrationStatus.PENDING,
                    OrchestrationStatus.RETRY_WAIT,
                    OrchestrationStatus.WAITING_DEPENDENCY,
                ]
            ),
        )
    ):
        pending_manual.status = OrchestrationStatus.CANCELLED
    pipelines = {
        p.key: p
        for p in session.scalars(
            select(PipelineDefinition).where(
                PipelineDefinition.key.in_(
                    [BINDINGS[c.capability_key][0] for c in caps if c.capability_key in BINDINGS]
                )
            )
        )
    }
    active_pipeline_ids = [p.id for p in pipelines.values()]
    schedules = session.scalars(
        select(ScheduleDefinition).where(
            ScheduleDefinition.tenant_id == policy.tenant_id,
            ScheduleDefinition.site_id == policy.site_id,
            ScheduleDefinition.pipeline_id.in_(active_pipeline_ids),
        )
    ).all()
    for old_schedule in schedules:
        old_schedule.status = ScheduleStatus.DISABLED
        old_schedule.next_scheduled_at = None
        pending = session.scalars(
            select(OrchestrationRun).where(
                OrchestrationRun.schedule_id == old_schedule.id,
                OrchestrationRun.status.in_(
                    [
                        OrchestrationStatus.PENDING,
                        OrchestrationStatus.RETRY_WAIT,
                        OrchestrationStatus.WAITING_DEPENDENCY,
                    ]
                ),
            )
        ).all()
        for run in pending:
            run.status = OrchestrationStatus.CANCELLED
            if run.obligation_id:
                obligation = session.get(OrchestrationObligation, run.obligation_id)
                if obligation:
                    obligation.status = ObligationStatus.BLOCKED
        for old_target in session.scalars(
            select(ScheduledTarget).where(ScheduledTarget.schedule_id == old_schedule.id)
        ):
            old_target.active = False
    seen: set[str] = set()
    for cap in caps:
        cp = cps.get(cap.id)
        if cp is None or not cp.enabled or cap.capability_key not in BINDINGS:
            continue
        pipeline_key, kind = BINDINGS[cap.capability_key]
        if pipeline_key in seen:  # LAB / FIELD share a single PageSpeed request.
            continue
        seen.add(pipeline_key)
        pipeline = pipelines.get(pipeline_key)
        if pipeline is None:
            pipeline = PipelineDefinition(
                key=pipeline_key,
                name=cap.display_name,
                handler_key="COLLECTOR_CLI",
                paid_provider=provider.is_commercial,
            )
            session.add(pipeline)
            session.flush()
        name = f"Provider {policy.id} {pipeline_key}"
        schedule = next((s for s in schedules if s.name == name), None)
        if schedule is None:
            schedule = ScheduleDefinition(
                tenant_id=policy.tenant_id,
                site_id=policy.site_id,
                pipeline_id=pipeline.id,
                name=name,
                cron_expression="0 8 * * *",
            )
            session.add(schedule)
        spec = CapabilityConfiguration(
            key=cap.capability_key, cadence=cp.cadence, **cp.schedule_configuration_json
        )
        schedule.cron_expression, schedule.timezone = cron(spec), policy.timezone
        schedule.data_source_connection_id = policy.data_source_connection_id
        schedule.freshness_sla_seconds = cp.freshness_target_seconds
        schedule.max_attempts = 2 if provider.is_commercial else 3
        schedule.retry_profile = "PAID_BOUNDED" if provider.is_commercial else "DAILY_FREE_API"
        schedule.automatic_catchup_seconds = 0 if provider.is_commercial else 86400
        schedule.policy_version = str(uuid.uuid4())
        schedule.configuration_json = {
            "provider_capability_policy_id": str(cp.id),
            "provider_policy_version": schedule.policy_version,
        }
        targets = session.scalars(
            select(ProviderCollectionTarget).where(
                ProviderCollectionTarget.capability_policy_id == cp.id,
                ProviderCollectionTarget.enabled.is_(True),
            )
        ).all()
        schedule.status = (
            ScheduleStatus.ENABLED
            if policy.master_enabled
            and policy.status == "ACTIVE"
            and cp.cadence != "MANUAL_ONLY"
            and targets
            else ScheduleStatus.DISABLED
        )
        schedule.next_scheduled_at = (
            next_occurrence(schedule.cron_expression, schedule.timezone, datetime.now(timezone.utc))
            if schedule.status == ScheduleStatus.ENABLED
            else None
        )
        session.flush()
        for target in targets:
            key = str(target.id)
            scheduled = session.scalar(
                select(ScheduledTarget).where(
                    ScheduledTarget.schedule_id == schedule.id,
                    ScheduledTarget.target_key == key,
                    ScheduledTarget.target_type == kind,
                )
            )
            if scheduled is None:
                scheduled = ScheduledTarget(
                    tenant_id=policy.tenant_id,
                    site_id=policy.site_id,
                    schedule_id=schedule.id,
                    target_type=kind,
                    target_key=key,
                )
                session.add(scheduled)
            scheduled.active = True
            scheduled.configuration_json = {"provider_target_id": key}


def guard_free_collection(
    session: Session, connection: DataSourceConnection, provider_key: str, target_value: str
) -> None:
    """Keep direct free CLI entrypoints subject to saved policy without changing legacy intent."""
    if not connection.site_id:
        raise ValueError("Free collection requires an explicit site connection")
    control = ProviderControlService(session)
    provider = control.provider(provider_key)
    policy = control.policy(connection.tenant_id, connection.site_id, provider.id)
    if policy is None:
        return  # Existing unconfigured free connections keep their pre-16B behavior.
    if (
        not policy.master_enabled
        or policy.status != "ACTIVE"
        or policy.data_source_connection_id != connection.id
    ):
        raise ValueError("Provider policy does not authorize this connection")
    enabled = session.scalars(
        select(ProviderCapabilityPolicy).where(
            ProviderCapabilityPolicy.collection_policy_id == policy.id,
            ProviderCapabilityPolicy.enabled.is_(True),
        )
    ).all()
    if not enabled:
        raise ValueError("Provider capabilities are disabled")
    if not any(cp.schedule_configuration_json for cp in enabled):
        return  # Migration-carried free policy not yet configured by an operator.
    for cp in enabled:
        for target in session.scalars(
            select(ProviderCollectionTarget).where(
                ProviderCollectionTarget.capability_policy_id == cp.id,
                ProviderCollectionTarget.enabled.is_(True),
                ProviderCollectionTarget.target_value == target_value,
            )
        ):
            if any(
                c["id"] == str(target.target_reference_id) and c["value"] == target_value
                for c in ConfigurationService(session).choices(
                    connection.tenant_id, connection.site_id, target.target_type
                )
            ):
                return
    raise ValueError("Target is not authorized by the current provider configuration")


def execution_arguments(
    session: Session, run: OrchestrationRun, pipeline: PipelineDefinition
) -> list[str] | None:
    """Re-resolve current policy at dispatch; queued snapshots cannot grant access."""
    binding_id = run.configuration_json.get("provider_capability_policy_id")
    if not binding_id:
        # Once a provider pipeline is controlled, obsolete jobs cannot bypass it.
        provider_key = {
            "gsc": "google_search_console",
            "ga4": "ga4",
            "experience": "google_pagespeed",
            "serp": "dataforseo",
            "external_search": "dataforseo",
        }.get(pipeline.key)
        if provider_key and run.site_id:
            control = ProviderControlService(session)
            provider = control.provider(provider_key)
            policy = control.policy(run.tenant_id, run.site_id, provider.id)
            if provider.is_commercial or (
                policy and (not policy.master_enabled or policy.status != "ACTIVE")
            ):
                raise ValueError(
                    "Provider execution is disabled or requires a current configuration binding."
                )
            if policy and session.scalar(
                select(ScheduleDefinition.id).where(
                    ScheduleDefinition.tenant_id == run.tenant_id,
                    ScheduleDefinition.site_id == run.site_id,
                    ScheduleDefinition.name.like(f"Provider {policy.id} %"),
                )
            ):
                raise ValueError(
                    "Legacy execution was superseded by the provider collection policy."
                )
        return None
    cp = session.get(ProviderCapabilityPolicy, uuid.UUID(str(binding_id)))
    policy = session.get(ProviderCollectionPolicy, cp.collection_policy_id) if cp else None
    target_id = run.configuration_json.get("provider_target_id")
    target = session.get(ProviderCollectionTarget, uuid.UUID(str(target_id))) if target_id else None
    if (
        not policy
        or not cp
        or not policy.site_id
        or policy.tenant_id != run.tenant_id
        or policy.site_id != run.site_id
    ):
        raise ValueError("Provider binding is outside the execution scope.")
    if not policy.master_enabled or policy.status != "ACTIVE" or not cp.enabled:
        raise ValueError("Provider collection is disabled or paused.")
    if not target or target.capability_policy_id != cp.id or not target.enabled:
        raise ValueError("This target is no longer authorized.")
    capability = session.get(ProviderCapability, cp.capability_id)
    if not capability or BINDINGS.get(capability.capability_key, (None, None))[0] != pipeline.key:
        raise ValueError("Capability does not authorize this pipeline.")
    choices = ConfigurationService(session).choices(
        policy.tenant_id, policy.site_id, target.target_type
    )
    if not any(
        c["id"] == str(target.target_reference_id)
        and c["value"] == target.target_value
        and c.get("eligible") is not False
        for c in choices
    ):
        raise ValueError("Canonical target changed or is no longer active; review configuration.")
    if run.schedule_id:
        schedule = session.get(ScheduleDefinition, run.schedule_id)
        if (
            not schedule
            or schedule.status != ScheduleStatus.ENABLED
            or schedule.policy_version != run.configuration_json.get("provider_policy_version")
        ):
            raise ValueError("The queued schedule was superseded by a policy change.")
    if (
        not policy.data_source_connection_id
        or policy.data_source_connection_id != run.data_source_connection_id
    ):
        raise ValueError("The configured connection changed; replan execution.")
    args = ["sync", "--connection", str(policy.data_source_connection_id)]
    if pipeline.key == "serp":
        args.extend(
            [
                "--query-id",
                str(target.metadata_json.get("execution_query_id", target.target_reference_id)),
            ]
        )
    elif pipeline.key in {"external_search", "builtwith_technology"}:
        args = [
            "keywords" if pipeline.key == "external_search" else "sync",
            "--connection",
            str(policy.data_source_connection_id),
            "--site",
            str(policy.site_id),
            "--domain",
            str(target.target_value),
        ]
    elif pipeline.key == "experience":
        args.extend(["--target", str(target.target_value)])
    if pipeline.key == "external_search":
        from gis.models import FailureCategory
        from gis.orchestration.reliability import ClassifiedFailure

        spec = CapabilityConfiguration(
            key=capability.capability_key, **cp.schedule_configuration_json
        )
        if spec.location_code is None or not spec.language_code:
            raise ClassifiedFailure(
                FailureCategory.CONFIGURATION_ERROR,
                "Domain Search request is missing required GIS location/language context. Configure the capability search market.",
            )
        args.extend(["--location-code", str(spec.location_code), "--language", spec.language_code])
    return args


def schedules_for(
    session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID, provider_id: uuid.UUID
) -> list[dict[str, Any]]:
    policy = ProviderControlService(session).policy(tenant_id, site_id, provider_id)
    if not policy:
        return []
    capabilities = {
        str(cp.id): (cp, cap)
        for cp, cap in session.execute(
            select(ProviderCapabilityPolicy, ProviderCapability)
            .join(
                ProviderCapability, ProviderCapability.id == ProviderCapabilityPolicy.capability_id
            )
            .where(ProviderCapabilityPolicy.collection_policy_id == policy.id)
        )
    }
    return [
        {
            "id": str(s.id),
            "status": s.status.value,
            "cron": s.cron_expression,
            "timezone": s.timezone,
            "next_at": s.next_scheduled_at,
            "policy_version": s.policy_version,
            "cadence": capabilities[str(s.configuration_json.get("provider_capability_policy_id"))][
                0
            ].cadence
            if str(s.configuration_json.get("provider_capability_policy_id")) in capabilities
            else None,
            "capability_key": capabilities[
                str(s.configuration_json.get("provider_capability_policy_id"))
            ][1].capability_key
            if str(s.configuration_json.get("provider_capability_policy_id")) in capabilities
            else None,
        }
        for s in session.scalars(
            select(ScheduleDefinition).where(
                ScheduleDefinition.tenant_id == tenant_id,
                ScheduleDefinition.site_id == site_id,
                ScheduleDefinition.name.like(f"Provider {policy.id} %"),
            )
        )
    ]
