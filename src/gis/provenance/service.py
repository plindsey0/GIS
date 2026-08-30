from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    DataAsset,
    DataAssetLineage,
    DataAssetSource,
    DataRightsGrant,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    PermittedUse,
    RightsDecision,
    RightsStatus,
)

LEGACY_USE_FIELDS: dict[PermittedUse, str] = {
    PermittedUse.INTERNAL_ANALYSIS: "deterministic_analysis_allowed",
    PermittedUse.COMMERCIAL_USE: "commercial_use_allowed",
    PermittedUse.RAW_RETENTION: "raw_storage_allowed",
    PermittedUse.NORMALIZED_RETENTION: "derived_storage_allowed",
    PermittedUse.DERIVATIVE_CREATION: "derived_storage_allowed",
    PermittedUse.AGGREGATE_STATISTICS: "aggregation_allowed",
    PermittedUse.EXTERNAL_PUBLICATION: "derived_display_allowed",
    PermittedUse.CUSTOMER_FACING_DISPLAY: "derived_display_allowed",
    PermittedUse.AI_INFERENCE: "ai_inference_allowed",
    PermittedUse.AI_TRAINING: "model_training_allowed",
}


@dataclass(frozen=True)
class RightsEvaluation:
    permitted_use: PermittedUse
    status: RightsStatus
    policy_id: uuid.UUID | None
    policy_version: str | None
    reason: str
    attribution_required: bool | None
    attribution_text: str | None = None
    contributors: tuple[RightsEvaluation, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "use": self.permitted_use.value,
            "status": self.status.value,
            "policy_id": str(self.policy_id) if self.policy_id else None,
            "policy_version": self.policy_version,
            "reason": self.reason,
            "attribution_required": self.attribution_required,
            "attribution_text": self.attribution_text,
            "contributors": [item.to_dict() for item in self.contributors],
        }


class RightsNotAllowedError(PermissionError):
    def __init__(self, evaluation: RightsEvaluation) -> None:
        super().__init__(
            f"{evaluation.permitted_use.value} is {evaluation.status.value}: {evaluation.reason}"
        )
        self.evaluation = evaluation


def _legacy_status(policy: DataRightsPolicy, permitted_use: PermittedUse) -> RightsStatus:
    field_name = LEGACY_USE_FIELDS.get(permitted_use)
    if field_name is None:
        return RightsStatus.UNKNOWN
    value = getattr(policy, field_name)
    if value is RightsDecision.ALLOWED:
        return RightsStatus.ALLOWED
    if value is RightsDecision.PROHIBITED:
        return RightsStatus.DENIED
    return RightsStatus.UNKNOWN


def evaluate_policy_use(
    session: Session, policy: DataRightsPolicy | None, permitted_use: PermittedUse
) -> RightsEvaluation:
    if policy is None:
        return RightsEvaluation(
            permitted_use,
            RightsStatus.UNKNOWN,
            None,
            None,
            "No applicable policy is documented.",
            None,
        )
    grant = (
        session.scalar(
            select(DataRightsGrant).where(
                DataRightsGrant.policy_id == policy.id,
                DataRightsGrant.permitted_use == permitted_use,
            )
        )
        if policy.id is not None
        else None
    )
    status = grant.status if grant else _legacy_status(policy, permitted_use)
    reason = (
        grant.reason
        if grant and grant.reason
        else (
            "Explicit policy grant."
            if grant
            else "Legacy policy mapping; unrepresented uses remain UNKNOWN."
        )
    )
    return RightsEvaluation(
        permitted_use,
        status,
        policy.id,
        policy.policy_version,
        reason,
        (
            True
            if policy.attribution_required is RightsDecision.ALLOWED
            else False
            if policy.attribution_required is RightsDecision.PROHIBITED
            else None
        ),
        policy.attribution_text,
    )


def evaluate_source_use(
    session: Session, source: DataSource, permitted_use: PermittedUse
) -> RightsEvaluation:
    policy = (
        session.get(DataRightsPolicy, source.default_rights_policy_id)
        if source.default_rights_policy_id
        else None
    )
    return evaluate_policy_use(session, policy, permitted_use)


def evaluate_connection_use(
    session: Session, connection: DataSourceConnection, permitted_use: PermittedUse
) -> RightsEvaluation:
    policy_id = connection.rights_policy_id
    if policy_id is None:
        source = session.get(DataSource, connection.data_source_id)
        policy_id = source.default_rights_policy_id if source else None
    return evaluate_policy_use(
        session, session.get(DataRightsPolicy, policy_id) if policy_id else None, permitted_use
    )


def aggregate_evaluations(
    permitted_use: PermittedUse, evaluations: list[RightsEvaluation]
) -> RightsEvaluation:
    if not evaluations:
        return RightsEvaluation(
            permitted_use,
            RightsStatus.UNKNOWN,
            None,
            None,
            "No contributing source policy was found.",
            None,
        )
    status = RightsStatus.ALLOWED
    if any(item.status is RightsStatus.DENIED for item in evaluations):
        status = RightsStatus.DENIED
    elif any(item.status is RightsStatus.UNKNOWN for item in evaluations):
        status = RightsStatus.UNKNOWN
    return RightsEvaluation(
        permitted_use,
        status,
        None,
        None,
        "Conservative aggregation: DENIED dominates UNKNOWN; UNKNOWN dominates ALLOWED.",
        (
            True
            if any(item.attribution_required is True for item in evaluations)
            else None
            if any(item.attribution_required is None for item in evaluations)
            else False
        ),
        contributors=tuple(evaluations),
    )


def upstream_assets(session: Session, asset_id: uuid.UUID) -> list[DataAsset]:
    result: list[DataAsset] = []
    seen = {asset_id}
    pending = [asset_id]
    while pending:
        current = pending.pop()
        edges = session.scalars(
            select(DataAssetLineage).where(DataAssetLineage.downstream_asset_id == current)
        ).all()
        for edge in edges:
            if edge.upstream_asset_id in seen:
                continue
            seen.add(edge.upstream_asset_id)
            pending.append(edge.upstream_asset_id)
            asset = session.get(DataAsset, edge.upstream_asset_id)
            if asset:
                result.append(asset)
    return result


def evaluate_asset_use(
    session: Session, asset: DataAsset, permitted_use: PermittedUse
) -> RightsEvaluation:
    assets = [asset, *upstream_assets(session, asset.id)]
    evaluations: list[RightsEvaluation] = []
    seen: set[tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None]] = set()
    for candidate in assets:
        links = session.scalars(
            select(DataAssetSource).where(DataAssetSource.asset_id == candidate.id)
        ).all()
        for link in links:
            key = (link.data_source_id, link.data_source_connection_id, link.rights_policy_id)
            if key in seen:
                continue
            seen.add(key)
            if link.rights_policy_id:
                evaluations.append(
                    evaluate_policy_use(
                        session, session.get(DataRightsPolicy, link.rights_policy_id), permitted_use
                    )
                )
            elif link.data_source_connection_id:
                connection = session.get(DataSourceConnection, link.data_source_connection_id)
                evaluations.append(
                    evaluate_connection_use(session, connection, permitted_use)
                    if connection
                    else evaluate_policy_use(session, None, permitted_use)
                )
            else:
                source = session.get(DataSource, link.data_source_id)
                evaluations.append(
                    evaluate_source_use(session, source, permitted_use)
                    if source
                    else evaluate_policy_use(session, None, permitted_use)
                )
    return aggregate_evaluations(permitted_use, evaluations)


def assert_use_allowed(evaluation: RightsEvaluation) -> None:
    if evaluation.status is not RightsStatus.ALLOWED:
        raise RightsNotAllowedError(evaluation)
