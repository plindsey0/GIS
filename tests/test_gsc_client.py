from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from gis.integrations.gsc.client import (
    GoogleHTTPTransport,
    GSCClient,
    GSCPermanentError,
    GSCTransientError,
)
from gis.integrations.gsc.config import CollectionGrain, GSCConnectionConfig


class FakeTransport:
    def __init__(self, pages: dict[int, list[dict[str, Any]]]) -> None:
        self.pages = pages
        self.bodies: list[dict[str, Any]] = []

    def query(self, property_uri: str, body: dict[str, Any]) -> dict[str, Any]:
        self.bodies.append(body)
        return {"rows": self.pages.get(body["startRow"], [])}

    def list_sites(self) -> list[dict[str, Any]]:
        return [{"siteUrl": "sc-domain:example.com", "permissionLevel": "siteOwner"}]


def config() -> GSCConnectionConfig:
    return GSCConnectionConfig(
        property_uri="sc-domain:example.com",
        collection_grain=CollectionGrain.PAGE,
    )


def test_pagination_collects_multiple_pages_and_terminates() -> None:
    transport = FakeTransport(
        {
            0: [{"keys": ["2026-08-20", "https://example.com/a"]}],
            1: [{"keys": ["2026-08-20", "https://example.com/b"]}],
            2: [],
        }
    )
    client = GSCClient(transport, row_limit=1)
    rows = list(client.iter_rows(config(), date(2026, 8, 20), date(2026, 8, 20)))
    assert len(rows) == 2
    assert [body["startRow"] for body in transport.bodies] == [0, 1, 2]


def test_pagination_stops_on_short_page() -> None:
    transport = FakeTransport({0: [{"keys": []}]})
    rows = list(
        GSCClient(transport, row_limit=2).iter_rows(config(), date(2026, 8, 20), date(2026, 8, 20))
    )
    assert len(rows) == 1
    assert len(transport.bodies) == 1


def test_zero_result_query_terminates() -> None:
    transport = FakeTransport({0: []})
    assert (
        list(GSCClient(transport).iter_rows(config(), date(2026, 8, 20), date(2026, 8, 20))) == []
    )
    assert len(transport.bodies) == 1


def test_pagination_safety_limit_raises() -> None:
    transport = FakeTransport({0: [{"keys": []}]})
    with pytest.raises(GSCTransientError):
        list(
            GSCClient(transport, row_limit=1, max_pages=1).iter_rows(
                config(), date(2026, 8, 20), date(2026, 8, 20)
            )
        )


def test_query_body_contains_dimensions_filters_and_search_type() -> None:
    transport = FakeTransport({0: []})
    configured = GSCConnectionConfig(
        property_uri="sc-domain:example.com",
        collection_grain=CollectionGrain.QUERY_PAGE,
        optional_dimensions=("country", "device", "searchAppearance"),
        country="usa",
        device="MOBILE",
    )
    list(GSCClient(transport).iter_rows(configured, date(2026, 8, 20), date(2026, 8, 20)))
    body = transport.bodies[0]
    assert body["dimensions"] == ["date", "query", "page", "country", "device", "searchAppearance"]
    assert body["type"] == "web"
    assert len(body["dimensionFilterGroups"][0]["filters"]) == 2


def test_property_validation_uses_exact_property_uri() -> None:
    client = GSCClient(FakeTransport({}))
    client.validate_property("sc-domain:example.com")


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return {}


class FakeHTTPSession:
    def __init__(self, statuses: list[int]) -> None:
        self.statuses = statuses
        self.calls = 0

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        status = self.statuses[self.calls]
        self.calls += 1
        return FakeResponse(status)


def test_transient_http_status_is_retried() -> None:
    session = FakeHTTPSession([429, 200])
    transport = GoogleHTTPTransport(session, max_attempts=2, sleeper=lambda _: None)  # type: ignore[arg-type]
    assert transport.query("sc-domain:example.com", {}) == {}
    assert session.calls == 2


def test_permanent_http_status_is_not_retried() -> None:
    session = FakeHTTPSession([403, 200])
    transport = GoogleHTTPTransport(session, max_attempts=2, sleeper=lambda _: None)  # type: ignore[arg-type]
    with pytest.raises(GSCPermanentError):
        transport.query("sc-domain:example.com", {})
    assert session.calls == 1
