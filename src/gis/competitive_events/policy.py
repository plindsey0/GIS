from __future__ import annotations

from decimal import Decimal
from typing import Any

POLICY_NAME = "gis-default-materiality"
POLICY_VERSION = "1.0.0"

DEFAULT_THRESHOLDS: dict[str, Any] = {
    "rank_movement_min": 3,
    "rank_thresholds": [3, 10, 20],
    "word_count_absolute_min": 100,
    "word_count_percent_min": "0.15",
    "visibility_absolute_min": "0.05",
    "visibility_percent_min": "0.15",
    "experience_absolute": {
        "LCP": "250",
        "INP": "50",
        "CLS": "0.05",
        "FCP": "250",
        "TTFB": "100",
        "PERFORMANCE_SCORE": "0.05",
        "ACCESSIBILITY_SCORE": "0.05",
        "BEST_PRACTICES_SCORE": "0.05",
        "SEO_SCORE": "0.05",
    },
    "cross_source_window_days": 14,
    "maximum_window_days": 366,
}


def decimal_thresholds(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    values = {**DEFAULT_THRESHOLDS, **(raw or {})}
    for key in ("word_count_percent_min", "visibility_absolute_min", "visibility_percent_min"):
        values[key] = Decimal(str(values[key]))
    values["experience_absolute"] = {
        key: Decimal(str(value)) for key, value in values["experience_absolute"].items()
    }
    return values
