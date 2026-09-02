from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.collection_planning.service import CollectionPlanningService
from gis.emerging_demand.service import EmergingDemandService
from gis.integrations.external_search.cli import estimate_cost
from gis.integrations.external_search.dataforseo import (
    COMPETITORS_URL,
    RANKED_KEYWORDS_URL,
    DataForSEOExternalSearchProvider,
    ExternalSearchProviderError,
    ProviderCollection,
    SearchRequest,
    normalize_domain,
)
from gis.integrations.external_search.service import (
    ExternalSearchCollector,
    normalize_keyword,
    normalize_ranking_url,
)
from gis.integrations.serp.cli import configure_connection
from gis.market_intelligence.service import MarketIntelligenceService
from gis.models import (
    CollectionTargetEvidence,
    ConnectionStatus,
    DataRightsPolicy,
    DemandObservation,
    ExternalCompetitorObservation,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    IngestionStatus,
    Organization,
    ProviderPricingConfiguration,
    RightsDecision,
    Site,
    Tenant,
    TrackedQuery,
)
from gis.provider_control.service import ProviderControlService
from gis.seed import seed

OBSERVED = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


class FakeProvider:
    def __init__(self, items: list[dict[str, Any]], *, task_id: str = "fixture-task") -> None:
        self.items = items
        self.task_id = task_id

    def collect(self, request: SearchRequest) -> ProviderCollection:
        return ProviderCollection(
            task_id=self.task_id,
            observed_at=OBSERVED,
            cost=Decimal("0.01224"),
            items=self.items,
            metadata={"fixture": True, "type": request.observation_type},
        )


class FakeResponse:
    status_code = 200

    def __init__(self, payload: object) -> None:
        self.payload = payload

    def json(self) -> object:
        return self.payload


class FakeHTTPSession:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(self.payload)


def ranking_item(position: int = 8) -> dict[str, Any]:
    return {
        "keyword_data": {
            "keyword": "VA Loan Calculator",
            "keyword_info": {
                "search_volume": 12100,
                "cpc": 2.75,
                "competition": 0.42,
                "competition_index": 42,
                "monthly_searches": [{"year": 2026, "month": 7, "search_volume": 11900}],
            },
            "keyword_properties": {"keyword_difficulty": 37},
            "search_intent_info": {"main_intent": "commercial"},
        },
        "ranked_serp_element": {
            "serp_item": {
                "type": "organic",
                "rank_absolute": position,
                "previous_rank_absolute": 10,
                "url": "https://www.vahomemath.com/calculator/?utm=x",
                "etv": 220.5,
            }
        },
    }


def competitor_item() -> dict[str, Any]:
    return {
        "domain": "example.com",
        "intersections": 25,
        "target_keywords": 100,
        "relevance": 0.75,
        "avg_position": 14.2,
        "full_domain_metrics": {"organic": {"count": 200, "etv": 900.4, "pos_1": 3}},
    }


def setup_scope(session: Session) -> tuple[Site, uuid.UUID]:
    seed(session, hostname="vahomemath.test")
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert site
    connection = configure_connection(
        session, "vahomemath", "vahomemath", "env:DATAFORSEO_CREDENTIAL_JSON"
    )
    connection.status = ConnectionStatus.ACTIVE
    control = ProviderControlService(session)
    provider = control.provider("dataforseo")
    capability = control.capability(provider.id, "DOMAIN_SEARCH_INTELLIGENCE")
    control.configure(
        site.tenant_id,
        site.id,
        "dataforseo",
        {
            "data_source_connection_id": connection.id,
            "monthly_hard_budget": Decimal("100"),
            "per_run_request_limit": 1,
            "allow_unknown_cost": True,
        },
        "test-admin",
        "fixture setup",
    )
    control.set_capability(
        site.tenant_id,
        site.id,
        "dataforseo",
        "DOMAIN_SEARCH_INTELLIGENCE",
        True,
        "MANUAL_ONLY",
        "test-admin",
    )
    control.add_target(
        site.tenant_id,
        site.id,
        "dataforseo",
        "DOMAIN_SEARCH_INTELLIGENCE",
        "DOMAIN",
        "vahomemath.test",
        "STANDARD",
        "test-admin",
    )
    session.add(
        ProviderPricingConfiguration(
            provider_id=provider.id,
            capability_id=capability.id,
            pricing_model="PER_REQUEST",
            unit_price=Decimal("0.01224"),
            units_per_price=Decimal("1"),
            currency="USD",
            provenance="TEST_FIXTURE",
            effective_start_at=datetime.now(timezone.utc),
        )
    )
    control.transition(site.tenant_id, site.id, "dataforseo", "ENABLE", "test-admin", None)
    session.flush()
    return site, connection.id


def request(kind: str = "ranked_keywords", domain: str = "vahomemath.test") -> SearchRequest:
    return SearchRequest(
        observation_type=kind,
        target_domain=domain,
        country_code="US",
        location_code=2840,
        language_code="en",
        device="desktop",
        limit=2,
    )


def test_normalization_and_cost_estimate() -> None:
    assert normalize_keyword(" VA  Loan\tCalculator ") == "va loan calculator"
    assert normalize_domain("https://WWW.Example.com/path") == "example.com"
    assert normalize_ranking_url("https://WWW.Example.com/a?q=1#x") == (
        "https://www.example.com/a",
        "example.com",
    )
    assert estimate_cost(2) == Decimal("0.01224000")
    with pytest.raises(ValueError):
        normalize_domain("localhost")


def test_dataforseo_request_mapping_and_response() -> None:
    payload = {
        "status_code": 20000,
        "tasks": [
            {
                "id": "task-1",
                "status_code": 20000,
                "cost": 0.01224,
                "result": [{"datetime": "2026-08-30T12:00:00Z", "items": [ranking_item()]}],
            }
        ],
    }
    transport = FakeHTTPSession(payload)
    provider = DataForSEOExternalSearchProvider(
        "login",
        "secret",
        session=transport,  # type: ignore[arg-type]
    )
    collection = provider.collect(request())
    assert transport.calls[0]["url"] == RANKED_KEYWORDS_URL
    body = transport.calls[0]["json"][0]
    assert body["target"] == "vahomemath.test" and body["location_code"] == 2840
    assert collection.task_id == "task-1" and collection.cost == Decimal("0.01224")
    assert "secret" not in str(transport.calls[0]["json"])


def test_dataforseo_competitor_request_and_malformed_response() -> None:
    transport = FakeHTTPSession({"status_code": 20000, "tasks": []})
    provider = DataForSEOExternalSearchProvider(
        "login",
        "secret",
        session=transport,  # type: ignore[arg-type]
    )
    with pytest.raises(ExternalSearchProviderError):
        provider.collect(request("competitors"))
    assert transport.calls[0]["url"] == COMPETITORS_URL
    assert transport.calls[0]["json"][0]["exclude_top_domains"] is True


def test_rankings_history_idempotency_cost_rights_and_isolation(session: Session) -> None:
    site, connection_id = setup_scope(session)
    first = ExternalSearchCollector(session, FakeProvider([ranking_item()])).sync(
        connection_id, site.id, request(), estimated_cost=Decimal("0.01224")
    )
    replay = ExternalSearchCollector(
        session, FakeProvider([ranking_item()], task_id="task-2")
    ).sync(connection_id, site.id, request(), estimated_cost=Decimal("0.01224"))
    changed = ExternalSearchCollector(
        session, FakeProvider([ranking_item(6)], task_id="task-3")
    ).sync(connection_id, site.id, request(), estimated_cost=Decimal("0.01224"))
    assert all(run.status is IngestionStatus.SUCCEEDED for run in (first, replay, changed))
    assert replay.records_inserted == 0 and replay.source_metadata["idempotent_replay"] is True
    observations = session.scalars(
        select(ExternalSearchObservation).order_by(ExternalSearchObservation.created_at)
    ).all()
    assert len(observations) == 2 and observations[0].effective_end is not None
    assert observations[1].effective_end is None
    ranking = session.scalar(
        select(ExternalKeywordRanking).where(
            ExternalKeywordRanking.external_search_observation_id == observations[1].id
        )
    )
    assert ranking and ranking.position == 6 and ranking.search_volume == 12100
    assert ranking.metric_semantics["estimated_traffic"] == "PROVIDER_ESTIMATED"
    assert observations[1].provider_reported_cost == Decimal("0.01224000")
    policy = session.get(DataRightsPolicy, observations[1].rights_policy_id)
    assert policy and policy.commercial_use_allowed is RightsDecision.UNKNOWN

    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    organization = session.scalar(select(Organization))
    assert tenant and organization
    other = Site(
        tenant_id=tenant.id,
        organization_id=organization.id,
        name="Other",
        slug="other",
        canonical_url="https://other.test",
        timezone="UTC",
    )
    session.add(other)
    session.commit()
    with pytest.raises(ValueError):
        ExternalSearchCollector(session, FakeProvider([ranking_item()])).sync(
            connection_id, other.id, request()
        )


def test_competitor_metrics_keep_provider_and_gis_semantics_separate(session: Session) -> None:
    site, connection_id = setup_scope(session)
    run = ExternalSearchCollector(session, FakeProvider([competitor_item()])).sync(
        connection_id, site.id, request("competitors")
    )
    assert run.status is IngestionStatus.SUCCEEDED
    row = session.scalar(select(ExternalCompetitorObservation))
    assert row and row.competitor_domain == "example.com"
    assert row.shared_keyword_count == 25
    assert row.gis_competitive_strength == Decimal("0.12500000")
    assert row.metric_semantics["relevance"] == "PROVIDER_DERIVED"
    assert row.metric_semantics["gis_competitive_strength"].startswith("GIS_DERIVED")


def test_malformed_canonical_item_persists_failed_run(session: Session) -> None:
    site, connection_id = setup_scope(session)
    run = ExternalSearchCollector(session, FakeProvider([{"keyword_data": {}}])).sync(
        connection_id, site.id, request()
    )
    assert run.status is IngestionStatus.FAILED and run.error_count == 1
    assert session.scalar(select(func.count()).select_from(ExternalSearchObservation)) == 0


def test_stored_external_keywords_feed_planning_and_monthly_demand(session: Session) -> None:
    site, connection_id = setup_scope(session)
    item = ranking_item()
    item["keyword_data"]["keyword_info"]["monthly_searches"] = [
        {"year": 2026, "month": month, "search_volume": 10_000 + month} for month in range(1, 5)
    ]
    ExternalSearchCollector(session, FakeProvider([item])).sync(
        connection_id, site.id, request(), estimated_cost=Decimal("0.01224")
    )
    observation = session.scalar(select(ExternalSearchObservation))
    assert observation
    # Legacy imports may carry only DataForSEO's canonical location code.
    observation.country_code = None
    policy = session.get(DataRightsPolicy, observation.rights_policy_id)
    assert policy
    policy.derived_storage_allowed = RightsDecision.ALLOWED
    session.commit()
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    assert tenant
    query = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="baseline market query",
        normalized_query="baseline market query",
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
        name="Stored external evidence market",
        slug=f"external-evidence-{uuid.uuid4()}",
        tracked_query_ids=[query.id],
    )
    planning = CollectionPlanningService(session)
    first = planning.discover(market)
    second = planning.discover(market)
    external_target = next(row for row in first if row.normalized_identity == "va loan calculator")
    assert {row.id for row in first} == {row.id for row in second}
    evidence = session.scalars(
        select(CollectionTargetEvidence).where(
            CollectionTargetEvidence.target_id == external_target.id,
            CollectionTargetEvidence.source_system == "EXTERNAL_SEARCH",
        )
    ).all()
    assert len(evidence) == 1
    demand = EmergingDemandService(session)
    assert demand.materialize_stored_evidence(market) == 5
    assert demand.materialize_stored_evidence(market) == 0
    observations = session.scalars(
        select(DemandObservation)
        .where(DemandObservation.collection_target_id == external_target.id)
        .order_by(DemandObservation.observed_date)
    ).all()
    assert [row.value for row in observations] == [
        Decimal("10001"),
        Decimal("10002"),
        Decimal("10003"),
        Decimal("10004"),
        Decimal("12100"),
    ]
    assert all(row.market_definition_version == market.version for row in observations)
    assert sum(row.provenance_metadata["historical_monthly_point"] for row in observations) == 4


def test_external_keyword_discovery_fails_closed_on_rights(session: Session) -> None:
    site, connection_id = setup_scope(session)
    ExternalSearchCollector(session, FakeProvider([ranking_item()])).sync(
        connection_id, site.id, request(), estimated_cost=Decimal("0.01224")
    )
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    assert tenant
    query = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="baseline market query",
        normalized_query="baseline market query",
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
        name="Rights closed market",
        slug=f"rights-closed-{uuid.uuid4()}",
        tracked_query_ids=[query.id],
    )
    targets = CollectionPlanningService(session).discover(market)
    assert all(row.normalized_identity != "va loan calculator" for row in targets)
