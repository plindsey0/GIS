"""Provider-scoped human authorization; never mutates computed planning decisions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    CollectionPlanItem,
    CollectionPlanningDecision,
    CollectionTarget,
    CollectionTargetEvidence,
    CollectionTargetStatus,
    CollectionTargetType,
    ProviderCollectionTarget,
    TrackedQuery,
)


def planning_choices(
    session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID, kind: str
) -> list[dict[str, Any]]:
    if kind not in {"QUERY", "DOMAIN", "URL"}:
        return []
    result = []
    for target in session.scalars(
        select(CollectionTarget)
        .where(
            CollectionTarget.tenant_id == tenant_id,
            CollectionTarget.site_id == site_id,
            CollectionTarget.target_type == CollectionTargetType(kind),
        )
        .order_by(CollectionTarget.display_value)
    ):
        decision = session.scalar(
            select(CollectionPlanningDecision)
            .where(CollectionPlanningDecision.target_id == target.id)
            .order_by(CollectionPlanningDecision.evaluated_at.desc())
            .limit(1)
        )
        plans = (
            list(
                session.scalars(
                    select(CollectionPlanItem).where(CollectionPlanItem.decision_id == decision.id)
                )
            )
            if decision
            else []
        )
        allowed = bool(plans) and all(p.rights_status.value == "ALLOWED" for p in plans)
        status = decision.computed_status.value if decision else target.status.value
        source = session.scalar(
            select(CollectionTargetEvidence.source_system)
            .where(CollectionTargetEvidence.target_id == target.id)
            .order_by(CollectionTargetEvidence.evidence_at)
            .limit(1)
        )
        eligible = (
            target.status in {CollectionTargetStatus.CANDIDATE, CollectionTargetStatus.ACTIVE}
            and allowed
            and bool(target.normalized_identity.strip())
        )
        result.append(
            {
                "id": str(target.id),
                "label": target.display_value,
                "value": target.normalized_identity,
                "type": kind,
                "computed_status": status,
                "computed_cadence": decision.computed_cadence.value if decision else "UNKNOWN",
                "priority": decision.priority_tier.value if decision else "UNKNOWN",
                "source": source or "UNKNOWN",
                "blocker": decision.primary_blocker.value if decision else "NOT_EVALUATED",
                "eligible": eligible,
                "unavailable_reason": None
                if eligible
                else "Rights must be allowed and the canonical target must be valid and active/candidate",
            }
        )
    return result


def authorization_metadata(
    session: Session,
    target: ProviderCollectionTarget,
    choice: dict[str, Any],
    cadence: str,
    actor: str,
    reason: str | None,
) -> None:
    previous = dict(target.metadata_json or {})
    target.metadata_json = {
        **previous,
        "human_override": True,
        "computed_status": choice.get("computed_status", "TRACKED"),
        "computed_cadence": choice.get("computed_cadence", "UNKNOWN"),
        "provider_cadence": cadence,
        "actor": actor,
        "reason": reason or "Explicit provider target authorization",
        "authorized_at": datetime.now(timezone.utc).isoformat(),
    }
    canonical = session.get(CollectionTarget, uuid.UUID(choice["id"]))
    if canonical and canonical.target_type == CollectionTargetType.QUERY:
        query = session.scalar(
            select(TrackedQuery).where(
                TrackedQuery.tenant_id == canonical.tenant_id,
                TrackedQuery.site_id == canonical.site_id,
                TrackedQuery.normalized_query == canonical.normalized_identity,
                TrackedQuery.device == (canonical.device or "desktop"),
                TrackedQuery.country_code == (canonical.country_code or "US"),
                TrackedQuery.language_code == (canonical.language_code or "en"),
                TrackedQuery.active.is_(True),
            )
        )
        if query is None:
            query = TrackedQuery(
                tenant_id=canonical.tenant_id,
                site_id=canonical.site_id,
                query_text=canonical.display_value,
                normalized_query=canonical.normalized_identity,
                device=canonical.device or "desktop",
                country_code=canonical.country_code or "US",
                language_code=canonical.language_code or "en",
            )
            session.add(query)
            session.flush()
        target.metadata_json = {**target.metadata_json, "execution_query_id": str(query.id)}
