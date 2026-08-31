from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median

from gis.models import DemandEvidenceStrength, DemandSignalType

POLICY_VERSION = "EMERGING_DEMAND_V1"
WINDOWS = {"SHORT": 7, "MEDIUM": 28, "LONG": 90}
MIN_POINTS_VELOCITY = 2
MIN_POINTS_ACCELERATION = 3
MIN_POINTS_EMERGENCE = 4
GROWTH_THRESHOLD = Decimal("0.15")
STABLE_THRESHOLD = Decimal("0.05")
ACCELERATION_THRESHOLD = Decimal("0.005")
SPIKE_MAD_MULTIPLIER = Decimal("3")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class Point:
    observed_date: date
    value: Decimal


@dataclass(frozen=True)
class TrendResult:
    signal_type: DemandSignalType
    current_value: Decimal | None
    prior_value: Decimal | None
    absolute_change: Decimal | None
    relative_change: Decimal | None
    velocity: Decimal | None
    prior_velocity: Decimal | None
    acceleration: Decimal | None
    strength: DemandEvidenceStrength
    reasons: tuple[str, ...]


def _velocity(left: Point, right: Point) -> Decimal | None:
    days = (right.observed_date - left.observed_date).days
    return (right.value - left.value) / Decimal(days) if days > 0 else None


def evidence_strength(
    point_count: int, corroborating_roles: int, continuous: bool
) -> DemandEvidenceStrength:
    if point_count < 2:
        return DemandEvidenceStrength.INSUFFICIENT
    if point_count < 4 or not continuous:
        return DemandEvidenceStrength.LIMITED
    if point_count >= 6 and corroborating_roles >= 2:
        return DemandEvidenceStrength.STRONGLY_SUPPORTED
    return DemandEvidenceStrength.SUPPORTED


def classify(
    points: list[Point],
    *,
    continuous: bool = True,
    regime_changed: bool = False,
    corroborating_roles: int = 0,
) -> TrendResult:
    ordered = sorted(points, key=lambda item: item.observed_date)
    strength = evidence_strength(len(ordered), corroborating_roles, continuous)
    if not ordered:
        return TrendResult(
            DemandSignalType.INSUFFICIENT_HISTORY,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            strength,
            ("No primary demand observations.",),
        )
    if len(ordered) == 1:
        return TrendResult(
            DemandSignalType.FIRST_OBSERVED,
            ordered[-1].value,
            None,
            None,
            None,
            None,
            None,
            None,
            strength,
            ("First observed by GIS; emergence is not established.",),
        )
    current, prior = ordered[-1], ordered[-2]
    absolute = current.value - prior.value
    relative = absolute / prior.value if prior.value > 0 else None
    velocity = _velocity(prior, current)
    prior_velocity = _velocity(ordered[-3], prior) if len(ordered) >= 3 else None
    acceleration = None
    if velocity is not None and prior_velocity is not None:
        elapsed = (current.observed_date - prior.observed_date).days
        acceleration = (velocity - prior_velocity) / Decimal(elapsed) if elapsed > 0 else None
    reasons: list[str] = []
    if regime_changed:
        reasons.append("Collection regime changed; directional classification is suppressed.")
        signal = DemandSignalType.INSUFFICIENT_HISTORY
    elif not continuous:
        reasons.append("Observation continuity is insufficient.")
        signal = DemandSignalType.INSUFFICIENT_HISTORY
    elif len(ordered) < MIN_POINTS_EMERGENCE:
        reasons.append("History is insufficient for sustained emergence classification.")
        signal = DemandSignalType.INSUFFICIENT_HISTORY
    else:
        baseline = ordered[:-1]
        baseline_values = [item.value for item in baseline]
        center = Decimal(str(median(baseline_values)))
        deviations = [abs(value - center) for value in baseline_values]
        mad = Decimal(str(median(deviations)))
        is_spike = mad > 0 and current.value > center + SPIKE_MAD_MULTIPLIER * mad
        recent_positive = all(
            ordered[index].value > ordered[index - 1].value
            for index in range(max(1, len(ordered) - 2), len(ordered))
        )
        if is_spike:
            signal = DemandSignalType.SPIKE
            reasons.append("Current value exceeds the versioned rolling median/MAD threshold.")
        elif (
            acceleration is not None and acceleration >= ACCELERATION_THRESHOLD and recent_positive
        ):
            signal = DemandSignalType.ACCELERATING
            reasons.append("Positive velocity increased across at least three comparable points.")
        elif relative is not None and relative >= GROWTH_THRESHOLD and recent_positive:
            low_baseline = min(baseline_values) <= max(Decimal(1), current.value * Decimal("0.10"))
            signal = DemandSignalType.EMERGING if low_baseline else DemandSignalType.GROWING
            reasons.append("Sustained comparable-period growth exceeded the policy threshold.")
        elif relative is not None and relative <= -GROWTH_THRESHOLD:
            signal = DemandSignalType.DECLINING
            reasons.append("Comparable-period decline exceeded the policy threshold.")
        elif relative is not None and abs(relative) <= STABLE_THRESHOLD:
            signal = DemandSignalType.STABLE
            reasons.append("Comparable-period change remained within the stability band.")
        elif acceleration is not None and acceleration <= -ACCELERATION_THRESHOLD:
            signal = DemandSignalType.DECELERATING
            reasons.append("Velocity decreased beyond the acceleration threshold.")
        else:
            signal = DemandSignalType.STABLE
            reasons.append("Change did not meet a sustained directional threshold.")
    return TrendResult(
        signal,
        current.value,
        prior.value,
        absolute,
        relative,
        velocity,
        prior_velocity,
        acceleration,
        strength,
        tuple(reasons),
    )
