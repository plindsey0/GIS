"""Deterministic temporal resolution from retained BuiltWith evidence."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.builtwith.provider import provider_date
from gis.models import (
    DataSource,
    DataSourceConnection,
    TechnologyDetection,
    TechnologyEvidence,
    TechnologyObservation,
)


@dataclass(frozen=True)
class EvidenceTemporal:
    first_observed: datetime | None
    last_observed: datetime | None
    first_raw: Any = None
    last_raw: Any = None


def evidence_temporal(evidence_value: str | None) -> EvidenceTemporal:
    """Read technology-level provider dates; path indexing dates are a different fact."""
    if not evidence_value:
        return EvidenceTemporal(None, None)
    try:
        value = json.loads(evidence_value)
    except (TypeError, ValueError):
        return EvidenceTemporal(None, None)
    technology = value.get("technology") if isinstance(value, dict) else None
    if not isinstance(technology, dict):
        return EvidenceTemporal(None, None)
    first_raw = technology.get("FirstDetected")
    last_raw = technology.get("LastDetected")
    return EvidenceTemporal(provider_date(first_raw), provider_date(last_raw), first_raw, last_raw)


def detection_temporal(
    session: Session, detection: TechnologyDetection
) -> tuple[datetime | None, datetime | None, list[EvidenceTemporal]]:
    evidence = [
        evidence_temporal(row.evidence_value)
        for row in session.scalars(
            select(TechnologyEvidence)
            .where(TechnologyEvidence.detection_id == detection.id)
            .order_by(TechnologyEvidence.id)
        )
    ]
    first_values = [item.first_observed for item in evidence if item.first_observed]
    last_values = [item.last_observed for item in evidence if item.last_observed]
    return (
        min(first_values) if first_values else None,
        max(last_values) if last_values else None,
        evidence,
    )


def backfill_temporal(
    session: Session,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    *,
    apply: bool = False,
) -> dict[str, int | bool]:
    """Backfill only normalized detection summaries from immutable retained evidence."""
    rows = list(
        session.scalars(
            select(TechnologyDetection)
            .join(TechnologyObservation)
            .join(DataSourceConnection)
            .join(DataSource)
            .where(
                TechnologyObservation.tenant_id == tenant_id,
                TechnologyObservation.site_id == site_id,
                DataSource.key == "builtwith",
            )
            .order_by(TechnologyDetection.id)
        )
    )
    changed = 0
    evidence_with_dates = 0
    for detection in rows:
        first_observed, last_observed, evidence = detection_temporal(session, detection)
        evidence_with_dates += sum(
            1 for item in evidence if item.first_observed or item.last_observed
        )
        if (
            detection.provider_first_seen_at != first_observed
            or detection.provider_last_seen_at != last_observed
        ):
            changed += 1
            if apply:
                detection.provider_first_seen_at = first_observed
                detection.provider_last_seen_at = last_observed
    if apply:
        session.commit()
    return {
        "detections_examined": len(rows),
        "detections_changed": changed,
        "evidence_items_with_temporal_values": evidence_with_dates,
        "applied": apply,
        "provider_calls": 0,
    }


def temporal_anomaly(
    last_observed: datetime | None, collected_at: datetime | None
) -> Optional[str]:
    if last_observed and collected_at and last_observed > collected_at:
        return "PROVIDER_DATE_AFTER_COLLECTION"
    return None
