from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.collection_planning.service import CollectionPlanningService
from gis.emerging_demand import cli
from gis.emerging_demand.analysis import Point, classify
from gis.emerging_demand.service import EmergingDemandService
from gis.market_intelligence.service import MarketIntelligenceService
from gis.models import (
    CollectionTargetEvidence,
    DataRightsPolicy,
    DemandCoverageState,
    DemandEntityType,
    DemandEvidenceStrength,
    DemandObservation,
    DemandSignal,
    DemandSignalType,
    DemandValidationRequest,
    EventSemanticClass,
    MarketDefinition,
    RightsDecision,
    ScheduleDefinition,
    Site,
    Tenant,
    TrackedQuery,
)
from gis.orchestration.seed import seed_vahomemath_cadence
from gis.seed import seed

NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


def test_first_observed_unknown_and_minimum_history() -> None:
    first = classify([Point(date(2026, 8, 1), Decimal(10))])
    assert first.signal_type is DemandSignalType.FIRST_OBSERVED
    assert first.relative_change is None
    assert first.strength is DemandEvidenceStrength.INSUFFICIENT
    two = classify([Point(date(2026, 8, 1), Decimal(10)), Point(date(2026, 8, 8), Decimal(20))])
    assert two.signal_type is DemandSignalType.INSUFFICIENT_HISTORY
    assert two.acceleration is None


def test_velocity_acceleration_decline_stability_and_spike() -> None:
    accelerating = classify(
        [
            Point(date(2026, 8, 1), Decimal(10)),
            Point(date(2026, 8, 8), Decimal(12)),
            Point(date(2026, 8, 15), Decimal(14)),
            Point(date(2026, 8, 22), Decimal(18)),
        ]
    )
    assert accelerating.velocity is not None and accelerating.acceleration is not None
    assert accelerating.signal_type is DemandSignalType.ACCELERATING
    declining = classify(
        [Point(date(2026, 8, day), value) for day, value in ((1, 100), (8, 90), (15, 80), (22, 60))]
    )
    assert declining.signal_type is DemandSignalType.DECLINING
    stable = classify([Point(date(2026, 8, day), Decimal(100)) for day in (1, 8, 15, 22)])
    assert stable.signal_type is DemandSignalType.STABLE
    spike = classify(
        [Point(date(2026, 8, day), value) for day, value in ((1, 10), (8, 11), (15, 9), (22, 100))]
    )
    assert spike.signal_type is DemandSignalType.SPIKE


def test_collection_regime_and_gaps_suppress_trends() -> None:
    points = [
        Point(date(2026, 8, day), value) for day, value in ((1, 10), (8, 12), (15, 15), (22, 20))
    ]
    assert (
        classify(points, regime_changed=True).signal_type is DemandSignalType.INSUFFICIENT_HISTORY
    )
    assert classify(points, continuous=False).signal_type is DemandSignalType.INSUFFICIENT_HISTORY


def scope(session: Session) -> tuple[Tenant, Site, MarketDefinition, DataRightsPolicy]:
    seed(session, hostname="vahomemath.test")
    seed_vahomemath_cadence(session)
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    query = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="emerging va query",
        normalized_query="emerging va query",
        country_code="US",
        language_code="en",
        device="desktop",
        requested_depth=100,
    )
    policy = DataRightsPolicy(
        tenant_id=tenant.id,
        name=f"demand-{uuid.uuid4()}",
        deterministic_analysis_allowed=RightsDecision.ALLOWED,
        derived_storage_allowed=RightsDecision.ALLOWED,
    )
    session.add_all([query, policy])
    session.flush()
    market = MarketIntelligenceService(session).define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Demand market",
        slug=f"demand-{uuid.uuid4()}",
        tracked_query_ids=[query.id],
    )
    session.flush()
    CollectionPlanningService(session).discover(market)
    session.flush()
    return tenant, site, market, policy


def add_observations(
    session: Session,
    tenant: Tenant,
    site: Site,
    market: MarketDefinition,
    policy: DataRightsPolicy,
    values: list[Decimal],
) -> None:
    target = CollectionPlanningService(session).discover(market)[0]
    for index, value in enumerate(values):
        observed = NOW - timedelta(days=7 * (len(values) - index - 1))
        identity = f"{target.id}:{observed.date()}:provider-volume"
        session.add(
            DemandObservation(
                tenant_id=tenant.id,
                site_id=site.id,
                market_definition_id=market.id,
                market_definition_version=market.version,
                collection_target_id=target.id,
                entity_type=DemandEntityType.QUERY,
                entity_key=target.normalized_identity,
                observed_date=observed.date(),
                observed_at=observed,
                source_system="test_provider",
                source_metric="SEARCH_VOLUME",
                value=value,
                unit="provider_searches",
                resolution_days=7,
                country_code="US",
                language_code="en",
                device="desktop",
                semantic_class=EventSemanticClass.PROVIDER_REPORTED,
                coverage_state=DemandCoverageState.OBSERVED,
                method_key="PROVIDER_VOLUME",
                method_version="1",
                rights_policy_id=policy.id,
                observation_key=uuid.uuid5(uuid.NAMESPACE_URL, identity).hex,
                content_hash=uuid.uuid5(uuid.NAMESPACE_OID, f"{identity}:{value}").hex,
                provenance_metadata={"fabricated": False, "test_fixture": True},
                effective_start=observed,
            )
        )
    session.flush()


def test_analysis_idempotency_planning_feedback_and_no_schedule_mutation(session: Session) -> None:
    tenant, site, market, policy = scope(session)
    add_observations(session, tenant, site, market, policy, [Decimal(10)])
    schedule_count = session.scalar(select(func.count()).select_from(ScheduleDefinition))
    service = EmergingDemandService(session)
    first = service.analyze(tenant.id, site.id, market.id, analyzed_at=NOW)
    second = service.analyze(tenant.id, site.id, market.id, analyzed_at=NOW)
    assert first.id == second.id
    signal = session.scalar(select(DemandSignal).where(DemandSignal.analysis_run_id == first.id))
    assert signal and signal.signal_type is DemandSignalType.FIRST_OBSERVED
    assert session.scalar(select(func.count()).select_from(DemandValidationRequest)) == 1
    assert (
        session.scalar(
            select(func.count())
            .select_from(CollectionTargetEvidence)
            .where(CollectionTargetEvidence.source_system == "emerging_demand")
        )
        == 1
    )
    assert session.scalar(select(func.count()).select_from(ScheduleDefinition)) == schedule_count


def test_rights_fail_closed_and_cli_dry_run_json(session: Session) -> None:
    tenant, site, market, policy = scope(session)
    policy.derived_storage_allowed = RightsDecision.UNKNOWN
    add_observations(session, tenant, site, market, policy, [Decimal(10), Decimal(12)])
    result = EmergingDemandService(session).analyze(tenant.id, site.id, market.id)
    assert result.observation_count == 0 and result.signal_count == 0
    payload = cli.run(
        [
            "analyze",
            "--tenant-id",
            str(tenant.id),
            "--site-id",
            str(site.id),
            "--market-id",
            str(market.id),
            "--dry-run",
        ],
        session,
    )
    assert payload["provider_calls"] == 0
    assert payload["schedules_mutated"] == 0


def test_series_compatibility_and_market_version_isolation(session: Session) -> None:
    tenant, site, market, policy = scope(session)
    add_observations(session, tenant, site, market, policy, [Decimal(10)])
    observation = session.scalar(select(DemandObservation))
    assert observation
    first = EmergingDemandService.series_key(observation)
    observation.device = "mobile"
    assert EmergingDemandService.series_key(observation) != first
    observation.device = "desktop"
    observation.market_definition_version += 1
    result = EmergingDemandService(session).analyze(tenant.id, site.id, market.id)
    assert result.observation_count == 0
