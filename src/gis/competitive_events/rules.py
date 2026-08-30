from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from gis.models import CompetitiveEventType, ExperienceMetric


@dataclass(frozen=True)
class Change:
    event_type: CompetitiveEventType
    subject_key: str
    magnitude: Decimal | None = None
    unit: str | None = None


def rank_change(
    subject: str, before: int | None, after: int | None, *, minimum: int, thresholds: list[int]
) -> Change | None:
    if before is None and after is not None:
        return Change(CompetitiveEventType.SERP_RANK_ENTERED, subject, Decimal(after), "rank")
    if before is not None and after is None:
        return Change(CompetitiveEventType.SERP_RANK_EXITED, subject, Decimal(before), "rank")
    if before is None or after is None or before == after:
        return None
    crossed = any(
        (before > boundary >= after) or (before <= boundary < after) for boundary in thresholds
    )
    movement = before - after
    if abs(movement) < minimum and not crossed:
        return None
    event_type = (
        CompetitiveEventType.SERP_RANK_INCREASED
        if movement > 0
        else CompetitiveEventType.SERP_RANK_DECREASED
    )
    return Change(event_type, subject, Decimal(abs(movement)), "positions")


def set_changes(
    before: set[str], after: set[str], gained: CompetitiveEventType, lost: CompetitiveEventType
) -> list[Change]:
    return [Change(gained, item) for item in sorted(after - before)] + [
        Change(lost, item) for item in sorted(before - after)
    ]


def material_numeric_change(
    subject: str,
    before: Decimal,
    after: Decimal,
    *,
    absolute_min: Decimal,
    percent_min: Decimal,
    increased: CompetitiveEventType,
    decreased: CompetitiveEventType,
    unit: str,
) -> Change | None:
    delta = after - before
    ratio = abs(delta) / abs(before) if before else (Decimal("1") if delta else Decimal("0"))
    if abs(delta) < absolute_min and ratio < percent_min:
        return None
    return Change(increased if delta > 0 else decreased, subject, abs(delta), unit)


def experience_change(
    subject: str, metric: ExperienceMetric, before: Decimal, after: Decimal, threshold: Decimal
) -> Change | None:
    delta = after - before
    if abs(delta) < threshold:
        return None
    lower_is_better = metric in {
        ExperienceMetric.LCP,
        ExperienceMetric.INP,
        ExperienceMetric.CLS,
        ExperienceMetric.FCP,
        ExperienceMetric.TTFB,
    }
    improved = delta < 0 if lower_is_better else delta > 0
    return Change(
        CompetitiveEventType.EXPERIENCE_METRIC_IMPROVED
        if improved
        else CompetitiveEventType.EXPERIENCE_METRIC_DEGRADED,
        subject,
        abs(delta),
        metric.value,
    )
