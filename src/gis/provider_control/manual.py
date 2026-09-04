"""Explicit preview/confirmation for manually queued provider work. Never calls a provider."""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    DataSourceConnection,
    OrchestrationRun,
    OrchestrationStatus,
    PermittedUse,
    PipelineDefinition,
    ProviderCapability,
    ProviderCapabilityPolicy,
    ProviderCollectionTarget,
    RightsStatus,
    TriggerType,
)
from gis.provenance.service import evaluate_connection_use
from gis.provider_control.configuration import (
    BINDINGS,
    CollectionConfiguration,
    ConfigurationService,
)


class ManualRequest(BaseModel):
    confirmed: bool = False
    fingerprint: str = ""
    request_id: uuid.UUID
    target_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)


def manual_run(
    session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID, key: str, request: ManualRequest
) -> dict[str, Any]:
    service = ConfigurationService(session)
    provider = service.control.provider(key)
    policy = service.control.policy(tenant_id, site_id, provider.id, lock=True)
    current = service.read(tenant_id, site_id, key)
    config = CollectionConfiguration.model_validate(
        {
            "policy": {**current["policy"], "actor": "workbench-admin"},
            "capabilities": current["capabilities"],
        }
    )
    blockers: list[str] = []
    selected = set(request.target_ids)
    if len(selected) != len(request.target_ids):
        raise ValueError("Duplicate manual targets are not allowed.")
    if not selected:
        blockers.append("Select at least one authorized target for this manual execution.")
    if not policy or not policy.master_enabled or policy.status != "ACTIVE":
        blockers.append("Collection must be explicitly activated before a manual run.")
    connection = (
        session.get(DataSourceConnection, policy.data_source_connection_id)
        if policy and policy.data_source_connection_id
        else None
    )
    if (
        selected
        and connection
        and evaluate_connection_use(session, connection, PermittedUse.NORMALIZED_RETENTION).status
        != RightsStatus.ALLOWED
    ):
        blockers.append("RIGHTS_BLOCKED")
    if (
        selected
        and connection
        and key == "builtwith"
        and evaluate_connection_use(session, connection, PermittedUse.RAW_RETENTION).status
        != RightsStatus.ALLOWED
    ):
        blockers.append("RAW_RETENTION_RIGHTS_BLOCKED")
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "config": config.model_dump(mode="json"),
                "state": policy.status if policy else None,
                "target_ids": sorted(str(t) for t in selected),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    jobs: list[tuple[ProviderCapabilityPolicy, ProviderCollectionTarget, str, Decimal | None]] = []
    choices: list[dict[str, Any]] = []
    found: set[uuid.UUID] = set()
    execution_keys: set[tuple[str, str]] = set()
    if policy:
        for cp, cap in session.execute(
            select(ProviderCapabilityPolicy, ProviderCapability)
            .join(
                ProviderCapability, ProviderCapability.id == ProviderCapabilityPolicy.capability_id
            )
            .where(
                ProviderCapabilityPolicy.collection_policy_id == policy.id,
                ProviderCapabilityPolicy.enabled.is_(True),
            )
        ):
            if cap.capability_key not in BINDINGS:
                continue
            pipeline_key = BINDINGS[cap.capability_key][0]
            for target in session.scalars(
                select(ProviderCollectionTarget).where(
                    ProviderCollectionTarget.capability_policy_id == cp.id,
                    ProviderCollectionTarget.enabled.is_(True),
                )
            ):
                choices.append(
                    {
                        "id": str(target.id),
                        "capability_key": cap.capability_key,
                        "capability_name": cap.display_name,
                        "target": target.target_value,
                        "cadence": cp.cadence,
                        "default_selected": False,
                        "search_market": {
                            "location_code": cp.schedule_configuration_json.get("location_code"),
                            "language_code": cp.schedule_configuration_json.get("language_code"),
                        }
                        if cap.capability_key == "DOMAIN_SEARCH_INTELLIGENCE"
                        else None,
                    }
                )
                if target.id not in selected:
                    continue
                found.add(target.id)
                canonical = service.choices(tenant_id, site_id, target.target_type)
                if not any(
                    c["id"] == str(target.target_reference_id)
                    and c["value"] == target.target_value
                    and c.get("eligible") is not False
                    for c in canonical
                ):
                    blockers.append("Canonical target changed or is no longer eligible.")
                check = service.control.preflight(
                    tenant_id,
                    site_id,
                    key,
                    cap.capability_key,
                    [target.target_value or ""],
                    1,
                    Decimal(1),
                )
                blockers.extend(check.blocking_reasons)
                # Some capabilities (PageSpeed LAB/FIELD) share one retrieval.
                # Keep every selected capability in scope, but never duplicate that request.
                execution_key = (pipeline_key, target.target_value or str(target.id))
                if execution_key not in execution_keys:
                    jobs.append((cp, target, pipeline_key, check.estimated_cost))
                    execution_keys.add(execution_key)
    if selected - found:
        blockers.append(
            "Selected targets are not authorized for an enabled capability in this scope."
        )
    if jobs:
        scoped = config.model_copy(deep=True)
        by_capability = {
            cp.capability_id: [
                t.target_reference_id for job_cp, t, _, _ in jobs if job_cp.id == cp.id
            ]
            for cp, _, _, _ in jobs
        }
        scoped.capabilities = [
            cap.model_copy(
                update={
                    "target_ids": by_capability[service.control.capability(provider.id, cap.key).id]
                }
            )
            for cap in scoped.capabilities
            if service.control.capability(provider.id, cap.key).id in by_capability
        ]
        blockers.extend(service.preview(tenant_id, site_id, key, scoped)["blockers"])
    total_cost = (
        None
        if any(j[3] is None for j in jobs)
        else sum((j[3] or Decimal(0) for j in jobs), Decimal(0))
    )
    warnings: list[str] = []
    if policy:
        batch_reasons: list[str] = []
        service.control._budget_reasons(policy, len(jobs), total_cost, batch_reasons, warnings)
        # Per-run ceilings were checked per target above; period limits cover the whole preview.
        blockers.extend(r for r in batch_reasons if not r.startswith("PER_RUN_"))
    result: dict[str, Any] = {
        "scope_contract_version": 1,
        "warnings": warnings,
        "choices": choices,
        "scope": [c for c in choices if uuid.UUID(c["id"]) in selected],
        "capabilities": len(
            {c["capability_key"] for c in choices if uuid.UUID(c["id"]) in selected}
        ),
        "targets": len(found),
        "fingerprint": fingerprint,
        "requests": len(jobs),
        "estimated_cost": str(total_cost) if total_cost is not None else None,
        "blockers": list(dict.fromkeys(blockers)),
        "queued": 0,
        "paid_calls_made": 0,
    }
    if not request.confirmed:
        return result
    if request.fingerprint != fingerprint:
        raise ValueError("Configuration changed after preview. Preview the run again.")
    if blockers or not policy or not jobs:
        raise ValueError("Manual run blocked: " + "; ".join(blockers or ["No authorized targets"]))
    previous = session.scalar(
        select(OrchestrationRun).where(
            OrchestrationRun.tenant_id == tenant_id,
            OrchestrationRun.site_id == site_id,
            OrchestrationRun.configuration_json["manual_execution_scope"]["request_id"].astext
            == str(request.request_id),
        )
    )
    if (
        previous
        and previous.configuration_json["manual_execution_scope"]["fingerprint"] != fingerprint
    ):
        raise ValueError("This request ID was already used for a different execution scope.")
    for cp, target, pipeline_key, estimate in jobs:
        pipeline = session.scalar(
            select(PipelineDefinition).where(PipelineDefinition.key == pipeline_key)
        )
        if not pipeline:
            raise ValueError("Configure the provider execution binding before running.")
        run_id = uuid.uuid5(request.request_id, f"{policy.id}:{target.id}")
        if session.get(OrchestrationRun, run_id):
            continue
        session.add(
            OrchestrationRun(
                id=run_id,
                tenant_id=tenant_id,
                site_id=site_id,
                pipeline_id=pipeline.id,
                data_source_connection_id=policy.data_source_connection_id,
                trigger_type=TriggerType.MANUAL,
                status=OrchestrationStatus.PENDING,
                estimated_provider_cost=estimate or Decimal(0),
                currency=policy.currency,
                configuration_json={
                    "provider_capability_policy_id": str(cp.id),
                    "provider_target_id": str(target.id),
                    "manual_execution_scope": {
                        "request_id": str(request.request_id),
                        "provider": key,
                        "actor": "workbench-admin",
                        "target_ids": sorted(str(t) for t in selected),
                        "items": result["scope"],
                        "fingerprint": fingerprint,
                    },
                    "request_count": 1,
                },
            )
        )
        result["queued"] += 1
    service.control._audit(
        policy,
        "MANUAL_RUN_QUEUED",
        "workbench-admin",
        "Explicit manual confirmation",
        {},
        {
            "request_id": str(request.request_id),
            "queued": result["queued"],
            "scope": result["scope"],
        },
    )
    session.flush()
    return result
