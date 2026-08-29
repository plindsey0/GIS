from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from requests import Response

from gis.integrations.ga4.client import (
    GA4Client,
    GA4PermanentError,
    GoogleGA4Transport,
)
from gis.integrations.ga4.config import GA4Dataset
from gis.integrations.ga4.reports import REPORTS


class PagingTransport:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.offsets: list[int] = []

    def run_report(self, property_resource: str, body: dict[str, Any]) -> dict[str, Any]:
        offset, limit = int(body["offset"]), int(body["limit"])
        self.offsets.append(offset)
        return {"rows": self.rows[offset : offset + limit], "rowCount": len(self.rows)}

    def get_property(self, property_resource: str) -> dict[str, Any]:
        return {"timeZone": "America/New_York"}


def test_iter_rows_paginates_until_row_count() -> None:
    transport = PagingTransport([{"row": number} for number in range(5)])
    rows = list(
        GA4Client(transport, page_limit=2).iter_rows(
            "properties/123", REPORTS[GA4Dataset.EVENTS], date(2026, 8, 1), date(2026, 8, 1)
        )
    )
    assert len(rows) == 5
    assert transport.offsets == [0, 2, 4]


def test_iter_rows_stops_on_short_page_or_empty_result() -> None:
    short = PagingTransport([{"row": 1}])
    assert (
        len(
            list(
                GA4Client(short, page_limit=2).iter_rows(
                    "properties/123",
                    REPORTS[GA4Dataset.EVENTS],
                    date(2026, 8, 1),
                    date(2026, 8, 1),
                )
            )
        )
        == 1
    )
    empty = PagingTransport([])
    assert (
        list(
            GA4Client(empty, page_limit=2).iter_rows(
                "properties/123",
                REPORTS[GA4Dataset.EVENTS],
                date(2026, 8, 1),
                date(2026, 8, 1),
            )
        )
        == []
    )


def test_validate_property_checks_metadata_and_report_access() -> None:
    transport = PagingTransport([])
    assert GA4Client(transport).validate_property("properties/123") == "America/New_York"
    assert transport.offsets == [0]


class FakeSession:
    def __init__(self, statuses: list[int]) -> None:
        self.statuses = statuses
        self.calls = 0

    def request(self, *args: Any, **kwargs: Any) -> Response:
        response = Response()
        response.status_code = self.statuses[self.calls]
        response._content = b"{}"
        self.calls += 1
        return response


def test_transport_retries_transient_errors() -> None:
    auth_session = FakeSession([429, 503, 200])
    transport = GoogleGA4Transport(auth_session, sleeper=lambda _: None)  # type: ignore[arg-type]
    assert transport.run_report("properties/123", {}) == {}
    assert auth_session.calls == 3


def test_transport_does_not_retry_permanent_errors() -> None:
    auth_session = FakeSession([403])
    transport = GoogleGA4Transport(auth_session, sleeper=lambda _: None)  # type: ignore[arg-type]
    with pytest.raises(GA4PermanentError, match="403"):
        transport.run_report("properties/123", {})
    assert auth_session.calls == 1
