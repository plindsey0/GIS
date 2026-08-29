from __future__ import annotations

from datetime import date
from pathlib import Path
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
    def __init__(self, statuses: list[int], bodies: list[bytes] | None = None) -> None:
        self.statuses = statuses
        self.bodies = bodies or [b"{}"] * len(statuses)
        self.calls = 0

    def request(self, *args: Any, **kwargs: Any) -> Response:
        response = Response()
        response.status_code = self.statuses[self.calls]
        response._content = self.bodies[self.calls]
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


def test_transport_includes_bounded_provider_error_detail() -> None:
    body = (
        b'{"error":{"code":400,"status":"INVALID_ARGUMENT","message":'
        b'"Field eventCountPerActiveUser is not a valid metric."}}'
    )
    auth_session = FakeSession([400], [body])
    transport = GoogleGA4Transport(auth_session, sleeper=lambda _: None)  # type: ignore[arg-type]
    with pytest.raises(GA4PermanentError) as caught:
        transport.run_report("properties/123", {})
    message = str(caught.value)
    assert message == (
        "GA4 HTTP 400: INVALID_ARGUMENT: Field eventCountPerActiveUser is not a valid metric."
    )
    assert len(message) < 600


def test_transport_falls_back_when_provider_error_is_malformed() -> None:
    auth_session = FakeSession([400], [b"not-json"])
    transport = GoogleGA4Transport(auth_session, sleeper=lambda _: None)  # type: ignore[arg-type]
    with pytest.raises(GA4PermanentError, match=r"^GA4 HTTP 400$"):
        transport.run_report("properties/123", {})


def test_event_report_requests_valid_count_per_user_metric() -> None:
    assert REPORTS[GA4Dataset.EVENTS].metrics == (
        "eventCount",
        "totalUsers",
        "eventCountPerUser",
        "keyEvents",
    )


def test_active_code_and_dbt_do_not_reference_invalid_metric() -> None:
    active_files = [*Path("src").rglob("*.py")]
    active_files.extend(Path("analytics/models").rglob("*.sql"))
    active_files.extend(Path("analytics/models").rglob("*.yml"))
    active_files.extend(Path("analytics/macros").rglob("*.sql"))
    active_files.extend(Path("analytics/tests").rglob("*.sql"))
    contents = "\n".join(path.read_text() for path in active_files)
    assert "eventCountPerActiveUser" not in contents
    assert "event_count_per_active_user" not in contents
