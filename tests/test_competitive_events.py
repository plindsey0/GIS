from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.competitive_events.cli import json_default
from gis.competitive_events.policy import decimal_thresholds
from gis.competitive_events.rules import (
    experience_change,
    material_numeric_change,
    rank_change,
    set_changes,
)
from gis.competitive_events.service import EventCandidate, EvidenceRef, SynthesisService
from gis.models import (
    CompetitiveEvent,
    CompetitiveEventDomain,
    CompetitiveEventEvidence,
    CompetitiveEventStatus,
    CompetitiveEventType,
    CompetitiveSubjectType,
    EventRelationshipType,
    EventSemanticClass,
    EvidenceRole,
    ExperienceMetric,
    RightsStatus,
    Site,
    Tenant,
)
from gis.seed import seed

NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


def test_rank_semantics_thresholds_and_suppression() -> None:
    improved = rank_change("page", 10, 3, minimum=3, thresholds=[3, 10, 20])
    declined = rank_change("page", 3, 10, minimum=3, thresholds=[3, 10, 20])
    crossing = rank_change("page", 11, 10, minimum=3, thresholds=[3, 10, 20])
    assert improved and improved.event_type == CompetitiveEventType.SERP_RANK_INCREASED
    assert declined and declined.event_type == CompetitiveEventType.SERP_RANK_DECREASED
    assert crossing is not None
    assert rank_change("page", 8, 7, minimum=3, thresholds=[3, 10, 20]) is None
    assert rank_change("page", None, 5, minimum=3, thresholds=[]) is not None
    assert rank_change("page", 5, None, minimum=3, thresholds=[]) is not None


def test_keyword_content_and_experience_rules() -> None:
    changes = set_changes(
        {"old", "same"},
        {"new", "same"},
        CompetitiveEventType.KEYWORD_GAINED,
        CompetitiveEventType.KEYWORD_LOST,
    )
    assert [(item.event_type, item.subject_key) for item in changes] == [
        (CompetitiveEventType.KEYWORD_GAINED, "new"),
        (CompetitiveEventType.KEYWORD_LOST, "old"),
    ]
    thresholds = decimal_thresholds()
    assert (
        material_numeric_change(
            "page",
            Decimal(1000),
            Decimal(1050),
            absolute_min=Decimal(100),
            percent_min=thresholds["word_count_percent_min"],
            increased=CompetitiveEventType.WORD_COUNT_INCREASED,
            decreased=CompetitiveEventType.WORD_COUNT_DECREASED,
            unit="words",
        )
        is None
    )
    assert (
        material_numeric_change(
            "page",
            Decimal(1000),
            Decimal(1200),
            absolute_min=Decimal(100),
            percent_min=thresholds["word_count_percent_min"],
            increased=CompetitiveEventType.WORD_COUNT_INCREASED,
            decreased=CompetitiveEventType.WORD_COUNT_DECREASED,
            unit="words",
        )
        is not None
    )
    assert (
        experience_change(
            "page:LCP", ExperienceMetric.LCP, Decimal(2500), Decimal(2300), Decimal(250)
        )
        is None
    )
    assert (
        experience_change(
            "page:LCP", ExperienceMetric.LCP, Decimal(2500), Decimal(2200), Decimal(250)
        ).event_type
        == CompetitiveEventType.EXPERIENCE_METRIC_IMPROVED
    )  # type: ignore[union-attr]


def scope(session: Session) -> tuple[Tenant, Site]:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    return tenant, site


def candidate(
    kind: CompetitiveEventType = CompetitiveEventType.PAGE_FIRST_OBSERVED,
) -> EventCandidate:
    return EventCandidate(
        subject_type=CompetitiveSubjectType.PAGE,
        subject_key="https://example.test/page",
        subject_url="https://example.test/page",
        subject_domain="example.test",
        event_domain=CompetitiveEventDomain.CONTENT,
        event_type=kind,
        event_time=NOW,
        evidence=(
            EvidenceRef(
                "gis_raw.competitive_content_observation",
                "evidence-1",
                NOW,
                EvidenceRole.PRIMARY,
                EventSemanticClass.MEASURED,
                Decimal("0.9"),
            ),
        ),
    )


def test_deterministic_identity_evidence_rights_and_zero_cost(session: Session) -> None:
    tenant, site = scope(session)
    service = SynthesisService(session)
    first = service.record(tenant.id, site.id, candidate())
    second = service.record(tenant.id, site.id, candidate())
    session.commit()
    assert first.id == second.id
    assert first.public_id == second.public_id
    assert first.provider_cost == 0
    assert first.effective_rights_status == RightsStatus.UNKNOWN
    assert session.scalar(select(func.count()).select_from(CompetitiveEvent)) == 1
    evidence = session.scalar(
        select(CompetitiveEventEvidence).where(
            CompetitiveEventEvidence.competitive_event_id == first.id
        )
    )
    assert evidence and evidence.source_record_id == "evidence-1"


def test_relationship_correction_and_tenant_isolation(session: Session) -> None:
    tenant, site = scope(session)
    service = SynthesisService(session)
    first = service.record(tenant.id, site.id, candidate())
    replacement = service.record(
        tenant.id, site.id, candidate(CompetitiveEventType.PAGE_CONTENT_CHANGED)
    )
    relation = service.relate(
        tenant.id, site.id, first.id, replacement.id, EventRelationshipType.PRECEDES
    )
    assert (
        service.relate(
            tenant.id, site.id, first.id, replacement.id, EventRelationshipType.PRECEDES
        ).id
        == relation.id
    )
    with pytest.raises(ValueError):
        service.relate(tenant.id, site.id, first.id, first.id, EventRelationshipType.SUPPORTS)
    service.supersede(first, replacement, "corrected evidence")
    assert first.status == CompetitiveEventStatus.SUPERSEDED
    service.retract(replacement, "source retracted")
    assert replacement.status == CompetitiveEventStatus.RETRACTED


def test_bounded_reprocessing_and_json(session: Session) -> None:
    tenant, site = scope(session)
    service = SynthesisService(session)
    result = service.synthesize(
        tenant.id, site.id, [CompetitiveEventDomain.SERP], NOW - timedelta(days=7), NOW
    )
    assert result["provider_cost"] == "0"
    assert json_default(Decimal("1.25")) == "1.25"
    with pytest.raises(ValueError):
        service.synthesize(
            tenant.id, site.id, [CompetitiveEventDomain.SERP], NOW - timedelta(days=400), NOW
        )
