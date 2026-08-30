from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from gis.models import (
    ExperienceAvailability,
    ExperienceMeasurementType,
    ExperienceMetric,
    ExperienceScope,
    FormFactor,
)

API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
FIELD_METRICS = {
    "LARGEST_CONTENTFUL_PAINT_MS": (ExperienceMetric.LCP, "ms"),
    "INTERACTION_TO_NEXT_PAINT": (ExperienceMetric.INP, "ms"),
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": (ExperienceMetric.CLS, "score"),
    "FIRST_CONTENTFUL_PAINT_MS": (ExperienceMetric.FCP, "ms"),
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": (ExperienceMetric.TTFB, "ms"),
}
LAB_AUDITS = {
    "largest-contentful-paint": (ExperienceMetric.LCP, "ms"),
    "interaction-to-next-paint": (ExperienceMetric.INP, "ms"),
    "cumulative-layout-shift": (ExperienceMetric.CLS, "score"),
    "first-contentful-paint": (ExperienceMetric.FCP, "ms"),
    "server-response-time": (ExperienceMetric.TTFB, "ms"),
}


@dataclass(frozen=True)
class NormalizedExperience:
    measurement_type: ExperienceMeasurementType
    scope: ExperienceScope
    form_factor: FormFactor
    availability: ExperienceAvailability
    metric: ExperienceMetric
    value: Decimal | None
    unit: str
    percentile: int | None = None
    classification: str | None = None
    good: Decimal | None = None
    needs: Decimal | None = None
    poor: Decimal | None = None


def normalize_target(value: str, scope: ExperienceScope) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("experience target must be absolute HTTP(S)")
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            "/" if scope is ExperienceScope.ORIGIN else parts.path or "/",
            "",
            "",
        )
    )


def _proportions(metric: dict[str, Any]) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    values = [Decimal(str(item.get("proportion", 0))) for item in metric.get("distributions", [])]
    return tuple((values + [None, None, None])[:3])  # type: ignore[return-value]


def normalize_pagespeed(
    payload: dict[str, Any], form_factor: FormFactor
) -> list[NormalizedExperience]:
    output: list[NormalizedExperience] = []
    for key, scope in (
        ("loadingExperience", ExperienceScope.URL),
        ("originLoadingExperience", ExperienceScope.ORIGIN),
    ):
        section = payload.get(key) or {}
        metrics = section.get("metrics") or {}
        for provider_name, (metric_name, unit) in FIELD_METRICS.items():
            metric = metrics.get(provider_name)
            if not metric:
                continue
            good, needs, poor = _proportions(metric)
            output.append(
                NormalizedExperience(
                    ExperienceMeasurementType.FIELD,
                    scope,
                    form_factor,
                    ExperienceAvailability.DATA_AVAILABLE,
                    metric_name,
                    Decimal(str(metric["percentile"])),
                    unit,
                    int(metric["percentile"]),
                    metric.get("category"),
                    good,
                    needs,
                    poor,
                )
            )
    lighthouse = payload.get("lighthouseResult") or {}
    audits = lighthouse.get("audits") or {}
    for provider_name, (metric_name, unit) in LAB_AUDITS.items():
        audit = audits.get(provider_name)
        if audit and audit.get("numericValue") is not None:
            output.append(
                NormalizedExperience(
                    ExperienceMeasurementType.LAB,
                    ExperienceScope.URL,
                    form_factor,
                    ExperienceAvailability.DATA_AVAILABLE,
                    metric_name,
                    Decimal(str(audit["numericValue"])),
                    unit,
                )
            )
    for category, metric in (
        ("performance", ExperienceMetric.PERFORMANCE_SCORE),
        ("accessibility", ExperienceMetric.ACCESSIBILITY_SCORE),
        ("best-practices", ExperienceMetric.BEST_PRACTICES_SCORE),
        ("seo", ExperienceMetric.SEO_SCORE),
    ):
        score = (lighthouse.get("categories") or {}).get(category, {}).get("score")
        if score is not None:
            output.append(
                NormalizedExperience(
                    ExperienceMeasurementType.LAB,
                    ExperienceScope.URL,
                    form_factor,
                    ExperienceAvailability.DATA_AVAILABLE,
                    metric,
                    Decimal(str(score)) * 100,
                    "score",
                )
            )
    if not output:
        output.append(
            NormalizedExperience(
                ExperienceMeasurementType.FIELD,
                ExperienceScope.URL,
                form_factor,
                ExperienceAvailability.INSUFFICIENT_DATA,
                ExperienceMetric.LCP,
                None,
                "ms",
            )
        )
    return output


class PageSpeedProvider:
    def __init__(
        self, api_key: str | None = None, *, session: requests.Session | None = None
    ) -> None:
        self.api_key, self.session = api_key, session or requests.Session()

    def collect(self, target: str, form_factor: FormFactor) -> tuple[dict[str, Any], datetime]:
        params: list[tuple[str, str]] = [("url", target), ("strategy", form_factor.value.lower())]
        for category in ("performance", "accessibility", "best-practices", "seo"):
            params.append(("category", category))
        if self.api_key:
            params.append(("key", self.api_key))
        response = self.session.get(API_URL, params=params, timeout=120)
        if response.status_code >= 400:
            raise RuntimeError(f"PageSpeed HTTP {response.status_code}")
        return response.json(), datetime.now(timezone.utc)


def cwv_classification(metric: ExperienceMetric, value: Decimal | None) -> str | None:
    if value is None:
        return None
    thresholds = {
        ExperienceMetric.LCP: (Decimal(2500), Decimal(4000)),
        ExperienceMetric.INP: (Decimal(200), Decimal(500)),
        ExperienceMetric.CLS: (Decimal("0.1"), Decimal("0.25")),
    }
    if metric not in thresholds:
        return None
    good, poor = thresholds[metric]
    return "GOOD" if value <= good else "NEEDS_IMPROVEMENT" if value <= poor else "POOR"
