"""Recovery reuses a failed execution/obligation and appends its next attempt."""

from __future__ import annotations

import hashlib
import os
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from gis.models import (
    DataSourceConnection,
    OrchestrationRun,
    OrchestrationStatus,
    PermittedUse,
    PipelineDefinition,
    ProviderCapability,
    ProviderCapabilityPolicy,
    ProviderCollectionPolicy,
    ProviderCollectionTarget,
    ProviderDefinition,
    RightsStatus,
)
from gis.provenance.service import evaluate_connection_use
from gis.provider_control.binding import execution_arguments
from gis.provider_control.credentials import dataforseo_credentials
from gis.provider_control.service import ProviderControlService


def recovery_preview(session: Session, run: OrchestrationRun) -> dict[str, Any]:
    blockers: list[str] = []
    pipeline = session.get(PipelineDefinition, run.pipeline_id)
    if (
        not pipeline
        or not run.site_id
        or not run.obligation_id
        or run.status not in {OrchestrationStatus.FAILED, OrchestrationStatus.BLOCKED}
    ):
        raise ValueError("Only failed or blocked provider obligations can be recovered")
    binding = run.configuration_json.get("provider_capability_policy_id")
    cp = session.get(ProviderCapabilityPolicy, uuid.UUID(str(binding))) if binding else None
    policy = session.get(ProviderCollectionPolicy, cp.collection_policy_id) if cp else None
    if not policy or not cp:
        raise ValueError("A current provider execution binding is required")
    provider = session.get(ProviderDefinition, policy.provider_id)
    if pipeline.paid_provider and os.environ.get("GIS_PAID_EXECUTION_DISABLED") == "1":
        blockers.append("Paid execution is held for no-call validation")
    cap = session.get(ProviderCapability, cp.capability_id)
    target = session.get(
        ProviderCollectionTarget, uuid.UUID(str(run.configuration_json.get("provider_target_id")))
    )
    connection = (
        session.get(DataSourceConnection, run.data_source_connection_id)
        if run.data_source_connection_id
        else None
    )
    try:
        execution_arguments(session, run, pipeline)
        if provider and provider.provider_key == "dataforseo":
            dataforseo_credentials(connection.credential_reference if connection else None)
    except (ValueError, RuntimeError) as exc:
        blockers.append(str(exc))
    if (
        not connection
        or evaluate_connection_use(session, connection, PermittedUse.NORMALIZED_RETENTION).status
        != RightsStatus.ALLOWED
    ):
        blockers.append("Rights are not allowed for this execution")
    if provider and cap and target:
        check = ProviderControlService(session).preflight(
            run.tenant_id,
            run.site_id,
            provider.provider_key,
            cap.capability_key,
            [target.target_value or ""],
            1,
            Decimal(1),
        )
        blockers.extend(check.blocking_reasons)
    fingerprint = hashlib.sha256(
        f"{run.id}:{run.status}:{run.completed_at}:{policy.updated_at}:{cp.updated_at}:{target.updated_at if target else None}".encode()
    ).hexdigest()
    return {
        "run_id": str(run.id),
        "obligation_id": str(run.obligation_id),
        "fingerprint": fingerprint,
        "blockers": blockers,
        "can_retry": not blockers,
        "requests": 1,
        "paid_calls_made": 0,
    }
