from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from typing import Any, Protocol

from google.auth.transport.requests import AuthorizedSession
from requests import Response
from requests.exceptions import RequestException

from gis.integrations.ga4.reports import ReportSpec

LOGGER = logging.getLogger(__name__)
DATA_API_ROOT = "https://analyticsdata.googleapis.com/v1beta"
ADMIN_API_ROOT = "https://analyticsadmin.googleapis.com/v1beta"


class GA4Error(RuntimeError):
    pass


class GA4TransientError(GA4Error):
    pass


class GA4PermanentError(GA4Error):
    pass


class GA4Transport(Protocol):
    def run_report(self, property_resource: str, body: dict[str, Any]) -> dict[str, Any]: ...

    def get_property(self, property_resource: str) -> dict[str, Any]: ...


class GoogleGA4Transport:
    def __init__(
        self,
        session: AuthorizedSession,
        *,
        max_attempts: int = 4,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session
        self.max_attempts = max_attempts
        self.sleeper = sleeper

    def run_report(self, property_resource: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._request(
            "POST", f"{DATA_API_ROOT}/{property_resource}:runReport", json=body
        )
        return _json_object(response)

    def get_property(self, property_resource: str) -> dict[str, Any]:
        response = self._request("GET", f"{ADMIN_API_ROOT}/{property_resource}")
        return _json_object(response)

    def _request(self, method: str, url: str, **kwargs: Any) -> Response:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response: Response = self.session.request(  # type: ignore[no-untyped-call]
                    method, url, timeout=60, **kwargs
                )
            except RequestException as error:
                last_error = error
                if attempt == self.max_attempts:
                    break
                self._backoff(attempt)
                continue
            if response.status_code == 429 or 500 <= response.status_code < 600:
                last_error = GA4TransientError(f"GA4 transient HTTP {response.status_code}")
                if attempt == self.max_attempts:
                    break
                self._backoff(attempt)
                continue
            if response.status_code >= 400:
                raise GA4PermanentError(f"GA4 HTTP {response.status_code}")
            return response
        raise GA4TransientError("GA4 request retries exhausted") from last_error

    def _backoff(self, attempt: int) -> None:
        delay = min(30.0, (2 ** (attempt - 1)) + random.uniform(0, 1))
        LOGGER.warning("ga4_retry", extra={"attempt": attempt, "delay_seconds": delay})
        self.sleeper(delay)


class GA4Client:
    def __init__(self, transport: GA4Transport, *, page_limit: int = 100_000) -> None:
        if page_limit < 1 or page_limit > 250_000:
            raise ValueError("page_limit must be between 1 and 250000")
        self.transport = transport
        self.page_limit = page_limit

    def property_timezone(self, property_resource: str) -> str:
        payload = self.transport.get_property(property_resource)
        timezone_name = payload.get("timeZone")
        if not isinstance(timezone_name, str) or not timezone_name:
            raise GA4PermanentError("GA4 property metadata did not include timeZone")
        return timezone_name

    def validate_property(self, property_resource: str) -> str:
        timezone_name = self.property_timezone(property_resource)
        end_date = date.today() - timedelta(days=3)
        self.transport.run_report(
            property_resource,
            {
                "dateRanges": [
                    {"startDate": end_date.isoformat(), "endDate": end_date.isoformat()}
                ],
                "dimensions": [{"name": "date"}],
                "metrics": [{"name": "activeUsers"}],
                "limit": "1",
                "offset": "0",
            },
        )
        return timezone_name

    def iter_rows(
        self,
        property_resource: str,
        report: ReportSpec,
        start_date: date,
        end_date: date,
    ) -> Iterator[dict[str, Any]]:
        offset = 0
        collected = 0
        while True:
            payload = self.transport.run_report(
                property_resource,
                {
                    "dateRanges": [
                        {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
                    ],
                    "dimensions": [{"name": name} for name in report.dimensions],
                    "metrics": [{"name": name} for name in report.metrics],
                    "limit": str(self.page_limit),
                    "offset": str(offset),
                    "keepEmptyRows": True,
                },
            )
            rows = payload.get("rows", [])
            if not isinstance(rows, list):
                raise GA4PermanentError("GA4 returned malformed rows")
            if not rows:
                return
            for row in rows:
                if not isinstance(row, dict):
                    raise GA4PermanentError("GA4 returned a malformed row")
                yield row
            returned = len(rows)
            collected += returned
            raw_count = payload.get("rowCount")
            if isinstance(raw_count, int) and collected >= raw_count:
                return
            if returned < self.page_limit:
                return
            offset += returned


def _json_object(response: Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as error:
        raise GA4PermanentError("GA4 returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise GA4PermanentError("GA4 returned a non-object response")
    return payload
