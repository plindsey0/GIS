from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gis.integrations.experience.pagespeed import (
    cwv_classification,
    normalize_pagespeed,
    normalize_target,
)
from gis.integrations.serp.cli import add_query
from gis.integrations.serp.dataforseo import (
    API_URL,
    DataForSEOProvider,
    DataForSEORequestError,
    DataForSEOResponseError,
)
from gis.integrations.serp.service import (
    SerpCollector,
    estimate_cost,
    map_feature,
    normalize_query,
    normalize_url,
)
from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    ExperienceAvailability,
    ExperienceMeasurementType,
    ExperienceMetric,
    ExperienceScope,
    FormFactor,
    IngestionStatus,
    RightsDecision,
    SerpFeatureType,
    SerpObservation,
    SerpResult,
    Site,
    Tenant,
    TrackedQuery,
)
from gis.seed import seed


class FakeSerpProvider:
    def __init__(self, url: str = "https://vahomemath.com/calculator?utm=x") -> None:
        self.url = url

    def collect(self, query: TrackedQuery) -> dict[str, Any]:
        return {
            "tasks": [
                {
                    "id": "fixture-task",
                    "cost": 0,
                    "result": [
                        {
                            "datetime": "2026-08-29T12:00:00Z",
                            "items": [
                                {
                                    "type": "organic",
                                    "rank_absolute": 2,
                                    "rank_group": 2,
                                    "url": self.url,
                                    "title": "VA loan calculator",
                                },
                                {"type": "people_also_ask", "rank_absolute": 3},
                            ],
                        }
                    ],
                }
            ]
        }


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> object:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeHTTPSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


def provider_query(**values: object) -> TrackedQuery:
    defaults: dict[str, object] = {
        "query_text": "va loan calculator",
        "normalized_query": "va loan calculator",
        "tenant_id": uuid.uuid4(),
        "site_id": uuid.uuid4(),
        "device": "desktop",
        "language_code": "en",
        "country_code": "US",
        "requested_depth": 100,
    }
    return TrackedQuery(**{**defaults, **values})


def setup_scope(session: Session) -> tuple[Tenant, Site, DataSourceConnection]:
    seed(session, hostname="vahomemath.com")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    source = session.scalar(select(DataSource).where(DataSource.key == "dataforseo"))
    assert tenant and site and source and source.default_rights_policy_id
    connection = DataSourceConnection(
        tenant_id=tenant.id,
        site_id=site.id,
        data_source_id=source.id,
        connection_type=ConnectionType.LICENSED_ENRICHMENT,
    )
    session.add(connection)
    session.commit()
    return tenant, site, connection


def test_query_normalization_mapping_and_url_validation() -> None:
    assert normalize_query("  VA  Loan\tRates ") == "va loan rates"
    assert map_feature("people_also_ask") is SerpFeatureType.PEOPLE_ALSO_ASK
    assert map_feature("new_provider_widget") is SerpFeatureType.OTHER
    assert map_feature("") is SerpFeatureType.UNKNOWN
    assert normalize_url("https://WWW.Example.com/a?q=1#x") == (
        "https://www.example.com/a",
        "example.com",
    )
    with pytest.raises(ValueError):
        normalize_url("javascript:alert(1)")


def test_tracked_query_registration_is_idempotent(session: Session) -> None:
    seed(session)
    first = add_query(session, "vahomemath", "vahomemath", " VA loan rates ")
    second = add_query(session, "vahomemath", "vahomemath", "va   LOAN rates")
    assert first.id == second.id
    assert session.scalars(select(TrackedQuery)).all() == [first]


def test_database_rejects_duplicate_context(session: Session) -> None:
    tenant, site, _ = setup_scope(session)
    values = dict(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="x",
        normalized_query="x",
        location_code=2840,
    )
    session.add_all([TrackedQuery(**values), TrackedQuery(**values)])
    with pytest.raises(IntegrityError):
        session.flush()


def test_dataforseo_request_mapping_does_not_include_credentials() -> None:
    query = TrackedQuery(
        query_text="va loan",
        normalized_query="va loan",
        tenant_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        device="mobile",
        language_code="en",
        country_code="US",
        location_code=2840,
        requested_depth=20,
    )
    provider = DataForSEOProvider("login", "secret")
    body = provider.request_body(query)
    assert API_URL.endswith("/serp/google/organic/live/advanced")
    assert body == [
        {
            "keyword": "va loan",
            "language_code": "en",
            "device": "mobile",
            "depth": 20,
            "location_code": 2840,
        }
    ]
    assert "secret" not in str(body)


def test_dataforseo_country_and_explicit_location_precedence() -> None:
    provider = DataForSEOProvider("login", "secret")
    assert provider.request_body(provider_query())[0]["location_code"] == 2840
    assert provider.request_body(provider_query(location_code=21176))[0]["location_code"] == 21176
    named = provider.request_body(provider_query(location_name="Austin,Texas,United States"))[0]
    assert named["location_name"] == "Austin,Texas,United States"
    assert "location_code" not in named


@pytest.mark.parametrize(
    "changes",
    [
        {"country_code": "ZZ"},
        {"query_text": " "},
        {"language_code": "english"},
        {"device": "tablet"},
        {"requested_depth": 201},
        {"location_code": 2840, "location_name": "United States"},
    ],
)
def test_invalid_dataforseo_request_never_calls_http(changes: dict[str, object]) -> None:
    transport = FakeHTTPSession(FakeResponse({}))
    provider = DataForSEOProvider("login", "secret", session=transport)  # type: ignore[arg-type]
    with pytest.raises(DataForSEORequestError):
        provider.collect(provider_query(**changes))
    assert transport.calls == []


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse(ValueError("bad json")), "valid JSON"),
        (FakeResponse([]), "must be an object"),
        (FakeResponse({"status_code": 40100, "status_message": "Authentication failed"}), "40100"),
        (FakeResponse({"status_code": 20000, "tasks": []}), "no tasks"),
        (
            FakeResponse(
                {
                    "status_code": 20000,
                    "tasks": [
                        {
                            "status_code": 40501,
                            "status_message": "Invalid Field: location",
                            "result": None,
                        }
                    ],
                }
            ),
            "task failed: 40501 Invalid Field: location",
        ),
    ],
)
def test_dataforseo_response_failures_are_meaningful(response: FakeResponse, message: str) -> None:
    transport = FakeHTTPSession(response)
    provider = DataForSEOProvider("login", "secret", session=transport)  # type: ignore[arg-type]
    with pytest.raises(DataForSEOResponseError, match=message):
        provider.collect(provider_query())


def test_dataforseo_http_failure_is_sanitized() -> None:
    response = FakeResponse(
        {"status_message": "password=secret Authorization=Basic-token"}, status_code=401
    )
    provider = DataForSEOProvider(
        "login",
        "secret",
        session=FakeHTTPSession(response),  # type: ignore[arg-type]
    )
    with pytest.raises(DataForSEOResponseError) as raised:
        provider.collect(provider_query())
    assert "secret" not in str(raised.value)
    assert "Basic-token" not in str(raised.value)


def test_serp_collection_provenance_ownership_and_revisions(session: Session) -> None:
    _, _, connection = setup_scope(session)
    query = add_query(session, "vahomemath", "vahomemath", "va loan calculator")
    first = SerpCollector(session, FakeSerpProvider()).sync(connection.id, query)
    second = SerpCollector(session, FakeSerpProvider()).sync(connection.id, query)
    assert first.status is IngestionStatus.SUCCEEDED and second.status is IngestionStatus.SUCCEEDED
    assert first.records_received == 2 and first.records_inserted == 2
    assert connection.status is ConnectionStatus.ACTIVE
    assert connection.last_successful_sync_at is not None
    observations = session.scalars(
        select(SerpObservation).order_by(SerpObservation.created_at)
    ).all()
    assert (
        len(observations) == 2
        and observations[0].effective_end is not None
        and observations[1].effective_end is None
    )
    results = session.scalars(
        select(SerpResult).where(SerpResult.serp_observation_id == observations[1].id)
    ).all()
    assert results[0].ownership.value == "OWN_SITE" and results[0].is_organic
    assert observations[1].rights_policy_id == source_policy_id(session, connection.data_source_id)


def test_failed_provider_run_never_leaks_secret(session: Session) -> None:
    _, _, connection = setup_scope(session)
    query = add_query(session, "vahomemath", "vahomemath", "failure")

    class Failure:
        def collect(self, query: TrackedQuery) -> dict[str, Any]:
            raise RuntimeError("credential supersecret")

    run = SerpCollector(session, Failure()).sync(connection.id, query)
    assert run.status is IngestionStatus.FAILED and run.error_summary == "RuntimeError"
    assert "supersecret" not in (run.error_summary or "")


def test_failed_task_null_result_persists_safe_diagnostic(session: Session) -> None:
    _, _, connection = setup_scope(session)
    query = add_query(session, "vahomemath", "vahomemath", "failed provider task")
    payload = {
        "status_code": 20000,
        "tasks": [
            {
                "status_code": 40501,
                "status_message": "Invalid Field: location",
                "result": None,
            }
        ],
    }
    provider = DataForSEOProvider(
        "login",
        "secret",
        session=FakeHTTPSession(FakeResponse(payload)),  # type: ignore[arg-type]
    )
    run = SerpCollector(session, provider).sync(connection.id, query)
    assert run.status is IngestionStatus.FAILED
    assert run.error_count == 1 and run.completed_at is not None
    assert run.error_summary == (
        "DataForSEOResponseError: task failed: 40501 Invalid Field: location"
    )
    assert run.source_metadata["provider_status_code"] == 40501
    assert connection.status is not ConnectionStatus.ACTIVE


def test_successful_empty_serp_activates_connection(session: Session) -> None:
    _, _, connection = setup_scope(session)
    query = add_query(session, "vahomemath", "vahomemath", "empty serp")
    payload = {
        "status_code": 20000,
        "tasks": [{"id": "empty-task", "status_code": 20000, "cost": 0.002, "result": []}],
    }
    provider = DataForSEOProvider(
        "login",
        "secret",
        session=FakeHTTPSession(FakeResponse(payload)),  # type: ignore[arg-type]
    )
    run = SerpCollector(session, provider).sync(connection.id, query)
    assert run.status is IngestionStatus.SUCCEEDED
    assert run.records_received == 0 and run.records_inserted == 0
    assert connection.status is ConnectionStatus.ACTIVE
    assert connection.last_successful_sync_at is not None


def test_cost_estimation_is_deterministic() -> None:
    estimate = estimate_cost(100, "WEEKLY", Decimal("0.002"))
    assert estimate.tasks == 435 and estimate.monthly_cost == Decimal("0.8700")


def test_pagespeed_field_lab_origin_and_insufficient_data() -> None:
    payload = {
        "loadingExperience": {
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {
                    "percentile": 2700,
                    "category": "AVERAGE",
                    "distributions": [
                        {"proportion": 0.7},
                        {"proportion": 0.2},
                        {"proportion": 0.1},
                    ],
                }
            }
        },
        "originLoadingExperience": {
            "metrics": {"INTERACTION_TO_NEXT_PAINT": {"percentile": 180, "category": "FAST"}}
        },
        "lighthouseResult": {
            "audits": {"cumulative-layout-shift": {"numericValue": 0.05}},
            "categories": {"performance": {"score": 0.9}},
        },
    }
    rows = normalize_pagespeed(payload, FormFactor.MOBILE)
    assert any(
        row.measurement_type is ExperienceMeasurementType.FIELD
        and row.scope is ExperienceScope.ORIGIN
        and row.metric is ExperienceMetric.INP
        for row in rows
    )
    assert any(
        row.measurement_type is ExperienceMeasurementType.LAB and row.metric is ExperienceMetric.CLS
        for row in rows
    )
    empty = normalize_pagespeed({}, FormFactor.DESKTOP)
    assert empty[0].availability is ExperienceAvailability.INSUFFICIENT_DATA
    assert (
        normalize_target("https://Example.com/a?q=1", ExperienceScope.ORIGIN)
        == "https://example.com/"
    )


def test_cwv_documented_thresholds() -> None:
    assert cwv_classification(ExperienceMetric.LCP, Decimal(2500)) == "GOOD"
    assert cwv_classification(ExperienceMetric.INP, Decimal(300)) == "NEEDS_IMPROVEMENT"
    assert cwv_classification(ExperienceMetric.CLS, Decimal("0.3")) == "POOR"


def test_seed_sources_remain_unknown(session: Session) -> None:
    seed(session)
    for key in ("dataforseo", "crux", "pagespeed"):
        source = session.scalar(select(DataSource).where(DataSource.key == key))
        assert source
        policy = session.get(DataRightsPolicy, source.default_rights_policy_id)
        assert policy and policy.commercial_use_allowed is RightsDecision.UNKNOWN


def source_policy_id(session: Session, source_id: uuid.UUID) -> uuid.UUID:
    source = session.get(DataSource, source_id)
    assert source and source.default_rights_policy_id
    return source.default_rights_policy_id
