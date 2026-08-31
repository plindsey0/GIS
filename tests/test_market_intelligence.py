from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.market_intelligence import cli
from gis.market_intelligence.analysis import (
    classify_intent,
    coverage_status,
    effective_competitor_count,
    hhi,
    participant_class,
    reciprocal_rank,
    shares,
)
from gis.market_intelligence.service import MarketIntelligenceService
from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    EventSemanticClass,
    IngestionRun,
    IngestionStatus,
    MarketDefinitionMember,
    MarketMetricObservation,
    MarketObservation,
    MarketParticipantClass,
    MarketParticipantObservation,
    MarketStatus,
    RightsDecision,
    SerpFeatureType,
    SerpObservation,
    SerpResult,
    Site,
    Tenant,
    TrackedQuery,
)
from gis.orchestration.seed import seed_vahomemath_cadence
from gis.seed import seed

DAY = date(2026, 8, 30)
NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


def scope(
    session: Session, decision: RightsDecision = RightsDecision.ALLOWED
) -> tuple[Tenant, Site, DataRightsPolicy, list[TrackedQuery]]:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    source = session.scalar(select(DataSource).where(DataSource.key == "dataforseo"))
    assert tenant and site and source
    policy = DataRightsPolicy(
        tenant_id=tenant.id,
        name=f"market-test-{uuid.uuid4()}",
        deterministic_analysis_allowed=decision,
        derived_storage_allowed=decision,
        aggregation_allowed=decision,
        derived_display_allowed=decision,
    )
    session.add(policy)
    session.flush()
    connection = DataSourceConnection(
        tenant_id=tenant.id,
        site_id=site.id,
        data_source_id=source.id,
        rights_policy_id=policy.id,
        connection_type=ConnectionType.LICENSED_ENRICHMENT,
        status=ConnectionStatus.ACTIVE,
        configuration_json={},
    )
    session.add(connection)
    session.flush()
    run = IngestionRun(
        tenant_id=tenant.id,
        site_id=site.id,
        data_source_connection_id=connection.id,
        started_at=NOW,
        completed_at=NOW,
        status=IngestionStatus.SUCCEEDED,
        records_received=4,
        records_inserted=4,
        records_rejected=0,
        error_count=0,
    )
    session.add(run)
    queries = [
        TrackedQuery(
            tenant_id=tenant.id,
            site_id=site.id,
            query_text="best calculator",
            normalized_query="best calculator",
            country_code="US",
            language_code="en",
            device="desktop",
            requested_depth=100,
        ),
        TrackedQuery(
            tenant_id=tenant.id,
            site_id=site.id,
            query_text="how to calculate",
            normalized_query="how to calculate",
            country_code="US",
            language_code="en",
            device="desktop",
            requested_depth=100,
        ),
    ]
    session.add_all(queries)
    session.flush()
    observations = []
    for index, query in enumerate(queries):
        observation = SerpObservation(
            tenant_id=tenant.id,
            site_id=site.id,
            tracked_query_id=query.id,
            ingestion_run_id=run.id,
            data_source_connection_id=connection.id,
            rights_policy_id=policy.id,
            rights_policy_version=policy.policy_version,
            observation_key=f"{index:064d}",
            observed_date=DAY,
            observed_at=NOW,
            search_engine="google",
            query_text=query.query_text,
            normalized_query=query.normalized_query,
            country_code="US",
            language_code="en",
            device="desktop",
            requested_depth=100,
            effective_start=NOW,
        )
        session.add(observation)
        session.flush()
        observations.append(observation)
    rows = [
        (observations[0], 1, "leader.test", "OTHER"),
        (observations[0], 3, "vahomemath.test", "OWN_SITE"),
        (observations[1], 2, "leader.test", "OTHER"),
        (observations[1], 10, "longtail.test", "OTHER"),
    ]
    for index, (observation, rank, hostname, ownership) in enumerate(rows):
        session.add(
            SerpResult(
                serp_observation_id=observation.id,
                rank_absolute=rank,
                feature_type=SerpFeatureType.ORGANIC,
                provider_type=f"organic-{index}",
                url=f"https://{hostname}/page-{index}",
                normalized_url=f"https://{hostname}/page-{index}",
                hostname=hostname,
                is_organic=True,
                ownership=ownership,
                provider_metadata={},
            )
        )
    session.flush()
    return tenant, site, policy, queries


def test_market_math_and_transparent_classification() -> None:
    assert reciprocal_rank(2) == Decimal("0.5")
    assert shares({"a": Decimal(3), "b": Decimal(1)}) == {
        "a": Decimal("0.75"),
        "b": Decimal("0.25"),
    }
    assert hhi([Decimal("0.75"), Decimal("0.25")]) == Decimal("0.6250")
    assert effective_competitor_count(Decimal("0.5")) == 2
    assert coverage_status(4, 2) == ("PARTIAL", Decimal("0.5"))
    assert participant_class(False, 2, 3)[0] == "DIRECT"
    assert participant_class(False, 1, 10)[0] == "PERIPHERAL"
    assert classify_intent("best mortgage calculator")[0] == "TOOL_CALCULATOR"


def test_frozen_definition_versioning_and_tenant_site_scope(session: Session) -> None:
    tenant, site, _, queries = scope(session)
    service = MarketIntelligenceService(session)
    first = service.define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Core",
        slug="core",
        tracked_query_ids=[item.id for item in queries],
    )
    first_members = session.scalar(
        select(func.count())
        .select_from(MarketDefinitionMember)
        .where(MarketDefinitionMember.market_definition_id == first.id)
    )
    second = service.define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Core",
        slug="core",
        tracked_query_ids=[queries[0].id],
    )
    assert first.version == 1 and first.status is MarketStatus.SUPERSEDED
    assert (first.country_code, first.language_code, first.device) == ("US", "en", "desktop")
    assert second.version == 2 and second.supersedes_id == first.id
    assert first_members == 2
    assert (
        session.scalar(
            select(func.count())
            .select_from(MarketDefinitionMember)
            .where(MarketDefinitionMember.market_definition_id == first.id)
        )
        == 2
    )
    other_tenant = Tenant(name="Other", slug=f"other-{uuid.uuid4()}", status="ACTIVE")
    session.add(other_tenant)
    session.flush()
    with pytest.raises(ValueError):
        service.define(
            tenant_id=other_tenant.id,
            site_id=site.id,
            name="Bad",
            slug="bad",
            tracked_query_ids=[queries[0].id],
        )


def test_definition_rejects_mixed_search_contexts(session: Session) -> None:
    tenant, site, _, queries = scope(session)
    queries[1].device = "mobile"
    session.flush()
    with pytest.raises(ValueError, match="cannot mix country, language, or device"):
        MarketIntelligenceService(session).define(
            tenant_id=tenant.id,
            site_id=site.id,
            name="Mixed context",
            slug="mixed-context",
            tracked_query_ids=[item.id for item in queries],
        )


def test_observation_history_visibility_concentration_coverage_and_cost(session: Session) -> None:
    tenant, site, policy, queries = scope(session)
    service = MarketIntelligenceService(session)
    definition = service.define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Core",
        slug="core",
        tracked_query_ids=[item.id for item in queries],
    )
    first = service.observe(definition, DAY, policy)
    replay = service.observe(definition, DAY, policy)
    assert replay.id == first.id and first.coverage_status.value == "COMPLETE"
    participants = session.scalars(
        select(MarketParticipantObservation).where(
            MarketParticipantObservation.market_observation_id == first.id
        )
    ).all()
    assert sum((item.visibility_share for item in participants), Decimal(0)) == pytest.approx(
        Decimal(1), abs=Decimal("0.000000001")
    )
    leader = next(item for item in participants if item.domain == "leader.test")
    owned = next(item for item in participants if item.domain == "vahomemath.test")
    assert leader.participant_class is MarketParticipantClass.DIRECT
    assert owned.participant_class is MarketParticipantClass.OWNED
    assert all(item.classification_version == "1.0.0" for item in participants)
    metrics = {
        item.metric_key: item
        for item in session.scalars(
            select(MarketMetricObservation).where(
                MarketMetricObservation.market_observation_id == first.id
            )
        ).all()
    }
    assert metrics["MARKET_HHI"].semantic_class is EventSemanticClass.GIS_DERIVED
    assert all(item.metric_definition_id is not None for item in metrics.values())
    assert metrics["TOTAL_PROVIDER_SEARCH_VOLUME"].metric_value is None
    assert metrics["TOTAL_PROVIDER_SEARCH_VOLUME"].provider == "external_search_provider"
    assert first.estimated_cost == 0 and first.provider_reported_cost is None
    assert first.provenance_metadata["definition_frozen"] is True


@pytest.mark.parametrize("decision", [RightsDecision.UNKNOWN, RightsDecision.PROHIBITED])
def test_rights_fail_closed_without_market_write(
    session: Session, decision: RightsDecision
) -> None:
    tenant, site, policy, queries = scope(session, decision)
    service = MarketIntelligenceService(session)
    definition = service.define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Core",
        slug="core",
        tracked_query_ids=[item.id for item in queries],
    )
    with pytest.raises(PermissionError):
        service.observe(definition, DAY, policy)
    assert session.scalar(select(func.count()).select_from(MarketObservation)) == 0


def test_sparse_coverage_and_definition_change_are_not_comparable(session: Session) -> None:
    tenant, site, policy, queries = scope(session)
    service = MarketIntelligenceService(session)
    definition = service.define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Core",
        slug="core",
        tracked_query_ids=[item.id for item in queries],
    )
    sparse = service.observe(definition, date(2026, 8, 29), policy)
    assert sparse.observed_query_count == 0
    assert sparse.coverage_status.value == "UNKNOWN"
    assert sparse.query_coverage_rate == 0
    revised = service.define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Core",
        slug="core",
        tracked_query_ids=[queries[0].id],
    )
    assert revised.id != definition.id and revised.version == 2


def test_cli_json_dry_run_and_disabled_zero_cost_orchestration(
    session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.run(["estimate", "--members", "5", "--dates", "2"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "bounded": True,
        "dates": 2,
        "estimated_provider_cost": "0",
        "members": 5,
        "provider_calls": 0,
    }
    _, _, _, _ = scope(session)
    schedules = seed_vahomemath_cadence(session)
    market = next(item for item in schedules if item.name == "Market intelligence weekly")
    assert market.status.value == "DISABLED"
    assert market.configuration_json["requires_operator_configuration"] is True
