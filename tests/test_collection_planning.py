from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.collection_planning import cli
from gis.collection_planning.analysis import (
    cadence_for,
    desired_status,
    priority_tier,
    score_components,
)
from gis.collection_planning.service import CollectionPlanningService, normalize_target
from gis.market_intelligence.service import MarketIntelligenceService
from gis.models import (
    CollectionBlocker,
    CollectionCadence,
    CollectionOverrideType,
    CollectionPlanItem,
    CollectionPlanningDecision,
    CollectionPriorityTier,
    CollectionTarget,
    CollectionTargetEvidence,
    CollectionTargetStatus,
    CollectionTargetType,
    ConnectionStatus,
    ConnectionType,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    MarketDefinition,
    RightsDecision,
    ScheduleDefinition,
    ScheduledTarget,
    ScheduleStatus,
    Site,
    Tenant,
    TrackedQuery,
)
from gis.orchestration.seed import seed_vahomemath_cadence
from gis.seed import seed

NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


def scope(session: Session) -> tuple[Tenant, Site, MarketDefinition]:
    seed(session, hostname="vahomemath.test")
    seed_vahomemath_cadence(session)
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    query = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="VA Loan Calculator",
        normalized_query="va loan calculator",
        country_code="US",
        language_code="en",
        device="desktop",
        requested_depth=100,
    )
    session.add(query)
    session.flush()
    market = MarketIntelligenceService(session).define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Test market",
        slug=f"test-market-{uuid.uuid4()}",
        tracked_query_ids=[query.id],
    )
    session.flush()
    return tenant, site, market


def allow_connection(session: Session, tenant: Tenant, site: Site, source_key: str) -> None:
    source = session.scalar(select(DataSource).where(DataSource.key == source_key))
    assert source
    policy = DataRightsPolicy(
        tenant_id=tenant.id,
        name=f"planning-allowed-{uuid.uuid4()}",
        deterministic_analysis_allowed=RightsDecision.ALLOWED,
        derived_storage_allowed=RightsDecision.ALLOWED,
        raw_storage_allowed=RightsDecision.ALLOWED,
    )
    session.add(policy)
    session.flush()
    session.add(
        DataSourceConnection(
            tenant_id=tenant.id,
            site_id=site.id,
            data_source_id=source.id,
            rights_policy_id=policy.id,
            connection_type=ConnectionType.NATIVE,
            status=ConnectionStatus.ACTIVE,
            configuration_json={},
        )
    )
    session.flush()


def test_normalization_and_unknown_aware_priority() -> None:
    assert normalize_target(CollectionTargetType.QUERY, " VA  Loan\nCalculator ")[0] == (
        "va loan calculator"
    )
    assert normalize_target(CollectionTargetType.DOMAIN, "HTTPS://WWW.Example.COM/path")[0] == (
        "example.com"
    )
    assert normalize_target(CollectionTargetType.URL, "https://Example.com/a/?utm_source=x")[0] == (
        "https://example.com/a/?utm_source=x"
    )
    score, unknown = score_components(
        {
            "market_relevance": Decimal(1),
            "owned_site_signal": None,
            "competitor_signal": None,
            "change_signal": None,
            "information_gap": Decimal(1),
            "strategic_seed": None,
        }
    )
    assert score == 1
    assert "owned_site_signal" in unknown
    assert priority_tier(score, 1) is CollectionPriorityTier.CRITICAL
    assert cadence_for(CollectionPriorityTier.HIGH) is CollectionCadence.MULTIPLE_PER_WEEK


def test_hysteresis_and_dormant_reactivation() -> None:
    assert (
        desired_status(CollectionTargetStatus.ACTIVE, Decimal("0.34"), 3)
        is CollectionTargetStatus.DORMANT
    )
    assert (
        desired_status(CollectionTargetStatus.DORMANT, Decimal("0.69"), 3)
        is CollectionTargetStatus.DORMANT
    )
    assert (
        desired_status(CollectionTargetStatus.DORMANT, Decimal("0.70"), 3)
        is CollectionTargetStatus.ACTIVE
    )
    assert (
        desired_status(CollectionTargetStatus.RETIRED, Decimal(1), 10)
        is CollectionTargetStatus.RETIRED
    )


def test_market_discovery_uniqueness_evidence_and_isolation(session: Session) -> None:
    tenant, site, market = scope(session)
    service = CollectionPlanningService(session)
    first = service.discover(market)
    second = service.discover(market)
    assert len(first) == len(second) == 1
    target = first[0]
    assert target.tenant_id == tenant.id and target.site_id == site.id
    assert target.market_definition_version == market.version
    assert (
        session.scalar(
            select(func.count())
            .select_from(CollectionTarget)
            .where(CollectionTarget.identity_hash == target.identity_hash)
        )
        == 1
    )
    service.seed_target(
        market, CollectionTargetType.QUERY, " va loan calculator ", "operator", "core seed"
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(CollectionTargetEvidence)
            .where(CollectionTargetEvidence.target_id == target.id)
        )
        == 2
    )
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4()}", status="ACTIVE")
    session.add(other)
    session.flush()
    original_tenant_id = market.tenant_id
    market.tenant_id = other.id
    with session.no_autoflush, pytest.raises(ValueError):
        service.seed_target(market, CollectionTargetType.QUERY, "bad", "operator", "bad")
    market.tenant_id = original_tenant_id


def test_plan_is_idempotent_and_distinguishes_rights_unknown_cost(session: Session) -> None:
    _, _, market = scope(session)
    service = CollectionPlanningService(session)
    service.discover(market)
    target = service.seed_target(
        market, CollectionTargetType.QUERY, "va loan calculator", "operator", "core seed"
    )
    first = service.plan(market)
    replay = service.plan(market)
    assert replay.id == first.id
    decision = session.scalar(
        select(CollectionPlanningDecision).where(CollectionPlanningDecision.target_id == target.id)
    )
    assert decision
    assert decision.computed_status is CollectionTargetStatus.ACTIVE
    assert decision.effective_status is CollectionTargetStatus.PAUSED
    items = session.scalars(
        select(CollectionPlanItem).where(CollectionPlanItem.decision_id == decision.id)
    ).all()
    assert any(item.rights_status.value == "UNKNOWN" for item in items)
    assert any(item.estimated_monthly_cost is None for item in items)
    assert CollectionBlocker.BLOCKED_BY_RIGHTS.value in decision.blockers_json


def test_allowed_free_collector_plan_apply_and_disabled_schedule(session: Session) -> None:
    tenant, site, market = scope(session)
    allow_connection(session, tenant, site, "direct_http")
    service = CollectionPlanningService(session)
    target = service.seed_target(
        market, CollectionTargetType.URL, "https://competitor.test/tool", "operator", "seed one"
    )
    service.seed_target(
        market, CollectionTargetType.URL, "https://competitor.test/tool", "operator", "seed two"
    )
    planning_run = service.plan(market)
    decision = session.scalar(
        select(CollectionPlanningDecision).where(CollectionPlanningDecision.target_id == target.id)
    )
    assert decision and decision.computed_status is CollectionTargetStatus.ACTIVE
    content_item = session.scalar(
        select(CollectionPlanItem)
        .join(
            CollectionPlanningDecision,
            CollectionPlanningDecision.id == CollectionPlanItem.decision_id,
        )
        .where(
            CollectionPlanningDecision.target_id == target.id,
            CollectionPlanItem.estimated_monthly_cost == 0,
            CollectionPlanItem.blocker == CollectionBlocker.NONE,
        )
    )
    assert content_item
    applied = service.apply(planning_run, "operator")
    assert applied
    scheduled = session.scalar(
        select(ScheduledTarget).where(ScheduledTarget.target_key == target.normalized_identity)
    )
    assert scheduled and scheduled.configuration_json["planning_decision_id"] == str(decision.id)
    schedule = session.get(ScheduleDefinition, scheduled.schedule_id)
    assert schedule and schedule.status is ScheduleStatus.DISABLED


def test_override_preserves_computed_and_changes_effective_plan(session: Session) -> None:
    _, _, market = scope(session)
    service = CollectionPlanningService(session)
    target = service.seed_target(
        market, CollectionTargetType.TOPIC, "Calculator tools", "operator", "seed one"
    )
    service.seed_target(
        market, CollectionTargetType.TOPIC, "calculator tools", "operator", "seed two"
    )
    service.set_override(
        target,
        CollectionOverrideType.FORCE_PAUSED,
        "reviewer",
        "manual research freeze",
    )
    service.plan(market)
    explanation = service.explain(target)
    assert explanation["computed_status"] is CollectionTargetStatus.ACTIVE
    assert explanation["effective_status"] is CollectionTargetStatus.PAUSED
    assert explanation["override"]["actor"] == "reviewer"
    cleared = service.clear_override(target, "reviewer")
    assert cleared and not cleared.active


def test_cli_json_dry_run_rolls_back(
    monkeypatch: pytest.MonkeyPatch, session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    _, _, market = scope(session)
    session.commit()
    monkeypatch.setattr(cli, "session_factory", lambda: lambda: Session(bind=session.get_bind()))
    before = session.scalar(select(func.count()).select_from(CollectionTarget))
    assert cli.run(["discover", str(market.id), "--dry-run"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["persisted"] is False and payload["provider_calls"] == 0
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(CollectionTarget)) == before
