"""Connection-scoped human reviews. Old policy/grant snapshots are never edited."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    DataRightsGrant,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    PermittedUse,
    RightsDecision,
    RightsStatus,
)
from gis.provenance.service import evaluate_policy_use

RIGHT_FIELDS = (
    "commercial_use_allowed",
    "third_party_processing_allowed",
    "deterministic_analysis_allowed",
    "ai_inference_allowed",
    "model_training_allowed",
    "raw_storage_allowed",
    "derived_storage_allowed",
    "raw_display_allowed",
    "derived_display_allowed",
    "aggregation_allowed",
    "cross_tenant_learning_allowed",
    "attribution_required",
)


class RightsReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_policy_id: Optional[uuid.UUID] = None
    review_authority: str = Field(min_length=1, max_length=255)
    documented_basis: str = Field(min_length=1, max_length=10000)
    policy_version: str = Field(min_length=1, max_length=100)
    effective_at: datetime
    decisions: dict[str, RightsDecision]
    grants: dict[PermittedUse, RightsStatus]
    retention_days: Optional[int] = Field(default=None, ge=0)
    attribution_text: Optional[str] = Field(default=None, max_length=10000)
    license_type: Optional[str] = Field(default=None, max_length=100)
    license_version: Optional[str] = Field(default=None, max_length=100)
    license_url: Optional[str] = Field(default=None, max_length=2048)
    jurisdiction_notes: Optional[str] = Field(default=None, max_length=10000)
    policy_notes: Optional[str] = Field(default=None, max_length=10000)


def scoped_connection(
    session: Session,
    connection_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    *,
    lock: bool = False,
) -> DataSourceConnection:
    query = select(DataSourceConnection).where(
        DataSourceConnection.id == connection_id,
        DataSourceConnection.tenant_id == tenant_id,
        DataSourceConnection.site_id == site_id,
    )
    connection = session.scalar(query.with_for_update() if lock else query)
    if connection is None:
        raise ValueError("Connection not found in site scope")
    return connection


def current_policy(
    session: Session, connection: DataSourceConnection
) -> Optional[DataRightsPolicy]:
    source = session.get(DataSource, connection.data_source_id)
    policy_id = connection.rights_policy_id or (source.default_rights_policy_id if source else None)
    return session.get(DataRightsPolicy, policy_id) if policy_id else None


def required_rights(session: Session, connection: DataSourceConnection) -> list[dict[str, object]]:
    source = session.get(DataSource, connection.data_source_id)
    if not source or source.key != "builtwith":
        return []
    policy = current_policy(session, connection)
    return [
        {
            "use": use.value,
            "label": label,
            "status": evaluation.status.value,
            "required": "ALLOWED",
            "blocking": evaluation.status != RightsStatus.ALLOWED,
        }
        for use, label in (
            (PermittedUse.RAW_RETENTION, "Raw storage"),
            (PermittedUse.NORMALIZED_RETENTION, "Derived storage"),
        )
        for evaluation in [evaluate_policy_use(session, policy, use)]
    ]


def review_context(session: Session, connection: DataSourceConnection) -> dict[str, object]:
    from gis.api.workbench import row_data

    policy = current_policy(session, connection)
    history = []
    seen = set()
    cursor = policy
    while cursor and cursor.id not in seen:
        seen.add(cursor.id)
        history.append(
            {
                **row_data(cursor),
                "grants": {
                    use.value: evaluate_policy_use(session, cursor, use).status.value
                    for use in PermittedUse
                },
            }
        )
        cursor = (
            session.get(DataRightsPolicy, cursor.supersedes_policy_id)
            if cursor.supersedes_policy_id
            else None
        )
    return {
        "connection_id": str(connection.id),
        "policy": row_data(policy) if policy else None,
        "decisions": {
            field: getattr(policy, field).value if policy else "UNKNOWN" for field in RIGHT_FIELDS
        },
        "grants": {
            use.value: evaluate_policy_use(session, policy, use).status.value
            for use in PermittedUse
        },
        "history": history,
    }


def review_policy(
    session: Session, connection: DataSourceConnection, payload: RightsReviewInput
) -> DataRightsPolicy:
    now = datetime.now(timezone.utc)
    old = current_policy(session, connection)
    if payload.expected_policy_id != (old.id if old else None):
        raise ValueError("Policy changed; reload and review the current version")
    if set(payload.decisions) != set(RIGHT_FIELDS) or set(payload.grants) != set(PermittedUse):
        raise ValueError("Review every supported right and permitted use independently")
    if payload.effective_at.tzinfo is None or payload.effective_at > now:
        raise ValueError("Effective date must be timezone-aware and not in the future")
    if old and old.policy_version == payload.policy_version:
        raise ValueError("A new review requires a new policy version")
    if payload.license_url:
        from urllib.parse import urlsplit

        url = urlsplit(payload.license_url)
        if (
            url.scheme != "https"
            or not url.netloc
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "License URL must be an HTTPS reference without credentials or query parameters"
            )
    values = payload.model_dump(exclude={"expected_policy_id", "decisions", "grants"})
    policy = DataRightsPolicy(
        **values,
        **payload.decisions,
        tenant_id=connection.tenant_id,
        name=f"Connection rights — {payload.policy_version}",
        reviewed_at=now,
        license_review_date=now.date(),
        supersedes_policy_id=old.id if old else None,
    )
    session.add(policy)
    session.flush()
    for use, status in payload.grants.items():
        session.add(
            DataRightsGrant(
                policy_id=policy.id,
                permitted_use=use,
                status=status,
                reason=payload.documented_basis,
            )
        )
    connection.rights_policy_id = policy.id
    session.flush()
    return policy
