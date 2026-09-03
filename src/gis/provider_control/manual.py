"""Explicit preview/confirmation for manually queued provider work. Never calls a provider."""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    OrchestrationRun,
    OrchestrationStatus,
    PipelineDefinition,
    ProviderCapability,
    ProviderCapabilityPolicy,
    ProviderCollectionTarget,
    TriggerType,
)
from gis.provider_control.configuration import (
    BINDINGS,
    CollectionConfiguration,
    ConfigurationService,
)


class ManualRequest(BaseModel):
    confirmed: bool = False
    fingerprint: str = ""
    request_id: uuid.UUID


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
    preview = service.preview(tenant_id, site_id, key, config)
    blockers = list(preview["blockers"])
    if not policy or not policy.master_enabled or policy.status != "ACTIVE":
        blockers.append("Collection must be explicitly activated before a manual run.")
    fingerprint = hashlib.sha256(
        json.dumps(
            {"config": config.model_dump(mode="json"), "state": policy.status if policy else None},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    jobs: list[tuple[ProviderCapabilityPolicy, ProviderCollectionTarget, str, Decimal | None]] = []
    seen: set[str] = set()
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
            pipeline_key = BINDINGS[cap.capability_key][0]
            if pipeline_key in seen:
                continue
            seen.add(pipeline_key)
            for target in session.scalars(
                select(ProviderCollectionTarget).where(
                    ProviderCollectionTarget.capability_policy_id == cp.id,
                    ProviderCollectionTarget.enabled.is_(True),
                )
            ):
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
                jobs.append((cp, target, pipeline_key, check.estimated_cost))
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
        "warnings": warnings,
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
        {"request_id": str(request.request_id), "queued": result["queued"]},
    )
    session.flush()
    return result
