from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

METHOD_KEY = "RECIPROCAL_RANK_VISIBILITY"
METHOD_VERSION = "1.0.0"
CLASSIFICATION_METHOD = "QUERY_OVERLAP_THRESHOLDS"
CLASSIFICATION_VERSION = "1.0.0"


def reciprocal_rank(position: int) -> Decimal:
    if position < 1:
        raise ValueError("position must be positive")
    return Decimal(1) / Decimal(position)


def shares(weights: dict[str, Decimal]) -> dict[str, Decimal]:
    total = sum(weights.values(), Decimal(0))
    if total <= 0:
        return {key: Decimal(0) for key in weights}
    return {key: value / total for key, value in weights.items()}


def hhi(values: Iterable[Decimal]) -> Decimal:
    return sum((value * value for value in values), Decimal(0))


def effective_competitor_count(concentration: Decimal) -> Decimal | None:
    return Decimal(1) / concentration if concentration > 0 else None


def coverage_status(configured: int, observed: int) -> tuple[str, Decimal]:
    if configured < 0 or observed < 0 or observed > configured:
        raise ValueError("invalid query coverage counts")
    if configured == 0:
        return "UNKNOWN", Decimal(0)
    rate = Decimal(observed) / Decimal(configured)
    if rate == 1:
        return "COMPLETE", rate
    if rate >= Decimal("0.5"):
        return "PARTIAL", rate
    if rate > 0:
        return "SPARSE", rate
    return "UNKNOWN", rate


def participant_class(owned: bool, query_count: int, observed_queries: int) -> tuple[str, Decimal]:
    overlap = Decimal(query_count) / Decimal(observed_queries) if observed_queries else Decimal(0)
    if owned:
        return "OWNED", overlap
    if query_count >= 2 and overlap >= Decimal("0.5"):
        return "DIRECT", overlap
    if overlap >= Decimal("0.2"):
        return "ADJACENT", overlap
    if query_count > 0:
        return "PERIPHERAL", overlap
    return "UNKNOWN", overlap


def classify_intent(query: str) -> tuple[str, Decimal]:
    normalized = f" {query.casefold().strip()} "
    rules = (
        ("TOOL_CALCULATOR", (" calculator ", " calculate ", " estimator ", " tool ")),
        ("LOCAL", (" near me ", " nearby ", " in my area ")),
        ("TRANSACTIONAL", (" buy ", " apply ", " quote ", " pricing ", " cost ")),
        ("COMMERCIAL_INVESTIGATION", (" best ", " compare ", " review ", " vs ", " versus ")),
        ("RESEARCH_DATA", (" statistics ", " dataset ", " research ", " study ", " report ")),
        ("INFORMATIONAL", (" how ", " what ", " why ", " guide ", " requirements ")),
        ("NAVIGATIONAL", (" login ", " official ", " website ")),
    )
    for label, needles in rules:
        if any(needle in normalized for needle in needles):
            return label, Decimal("0.75")
    return "UNKNOWN", Decimal("0.25")
