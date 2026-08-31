from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from gis.models import (
    CollectionCadence,
    CollectionPriorityTier,
    CollectionTargetStatus,
)

PRIORITY_POLICY_KEY = "COLLECTION_PRIORITY"
PRIORITY_POLICY_VERSION = "COLLECTION_PRIORITY_V1"
CADENCE_POLICY_VERSION = "COLLECTION_CADENCE_V1"

DEFAULT_WEIGHTS = {
    "market_relevance": Decimal("0.30"),
    "owned_site_signal": Decimal("0.20"),
    "competitor_signal": Decimal("0.15"),
    "change_signal": Decimal("0.10"),
    "information_gap": Decimal("0.15"),
    "strategic_seed": Decimal("0.10"),
}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def score_components(
    components: dict[str, Decimal | None],
    weights: dict[str, Decimal] | None = None,
) -> tuple[Decimal, list[str]]:
    configured = weights or DEFAULT_WEIGHTS
    known = {key: value for key, value in components.items() if value is not None}
    denominator = sum((configured[key] for key in known), Decimal(0))
    if denominator == 0:
        return Decimal(0), sorted(set(configured) - set(known))
    score = sum((configured[key] * value for key, value in known.items()), Decimal(0))
    return min(Decimal(1), max(Decimal(0), score / denominator)), sorted(
        set(configured) - set(known)
    )


def priority_tier(score: Decimal, evidence_count: int) -> CollectionPriorityTier:
    if evidence_count == 0:
        return CollectionPriorityTier.DORMANT
    if score >= Decimal("0.90"):
        return CollectionPriorityTier.CRITICAL
    if score >= Decimal("0.75"):
        return CollectionPriorityTier.HIGH
    if score >= Decimal("0.55"):
        return CollectionPriorityTier.MEDIUM
    if score >= Decimal("0.35"):
        return CollectionPriorityTier.LOW
    return CollectionPriorityTier.DISCOVERY


def desired_status(
    current: CollectionTargetStatus, score: Decimal, evidence_count: int
) -> CollectionTargetStatus:
    if current in {CollectionTargetStatus.RETIRED, CollectionTargetStatus.REJECTED}:
        return current
    if evidence_count < 2:
        return CollectionTargetStatus.CANDIDATE
    if current is CollectionTargetStatus.ACTIVE:
        return (
            CollectionTargetStatus.DORMANT
            if score < Decimal("0.35")
            else CollectionTargetStatus.ACTIVE
        )
    if current is CollectionTargetStatus.DORMANT:
        return (
            CollectionTargetStatus.ACTIVE
            if score >= Decimal("0.70")
            else CollectionTargetStatus.DORMANT
        )
    return (
        CollectionTargetStatus.ACTIVE
        if score >= Decimal("0.65")
        else CollectionTargetStatus.CANDIDATE
    )


def cadence_for(tier: CollectionPriorityTier) -> CollectionCadence:
    return {
        CollectionPriorityTier.CRITICAL: CollectionCadence.DAILY,
        CollectionPriorityTier.HIGH: CollectionCadence.MULTIPLE_PER_WEEK,
        CollectionPriorityTier.MEDIUM: CollectionCadence.WEEKLY,
        CollectionPriorityTier.LOW: CollectionCadence.MONTHLY,
        CollectionPriorityTier.DISCOVERY: CollectionCadence.ON_DEMAND,
        CollectionPriorityTier.DORMANT: CollectionCadence.NONE,
    }[tier]


RUNS_PER_MONTH = {
    CollectionCadence.DAILY: Decimal("30.4375"),
    CollectionCadence.MULTIPLE_PER_WEEK: Decimal("8.7"),
    CollectionCadence.WEEKLY: Decimal("4.35"),
    CollectionCadence.MONTHLY: Decimal(1),
    CollectionCadence.ON_DEMAND: Decimal(0),
    CollectionCadence.NONE: Decimal(0),
}


CRON_BY_CADENCE = {
    CollectionCadence.DAILY: "0 7 * * *",
    CollectionCadence.MULTIPLE_PER_WEEK: "0 7 * * 1,4",
    CollectionCadence.WEEKLY: "0 7 * * 1",
    CollectionCadence.MONTHLY: "0 7 1 * *",
    CollectionCadence.ON_DEMAND: "0 7 1 1 *",
    CollectionCadence.NONE: "0 7 1 1 *",
}
