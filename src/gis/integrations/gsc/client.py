from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Iterator
from datetime import date
from typing import Any, Protocol
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession
from requests import Response
from requests.exceptions import RequestException

from gis.integrations.gsc.config import GSCConnectionConfig

LOGGER = logging.getLogger(__name__)
API_ROOT = "https://www.googleapis.com/webmasters/v3"


class GSCError(RuntimeError):
    pass


class GSCTransientError(GSCError):
    pass


class GSCPermanentError(GSCError):
    pass


class GSCPageTransport(Protocol):
    def query(self, property_uri: str, body: dict[str, Any]) -> dict[str, Any]: ...

    def list_sites(self) -> list[dict[str, Any]]: ...


class GoogleHTTPTransport:
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

    def query(self, property_uri: str, body: dict[str, Any]) -> dict[str, Any]:
        encoded = quote(property_uri, safe="")
        response = self._request(
            "POST", f"{API_ROOT}/sites/{encoded}/searchAnalytics/query", json=body
        )
        return _json_object(response)

    def list_sites(self) -> list[dict[str, Any]]:
        response = self._request("GET", f"{API_ROOT}/sites")
        payload = _json_object(response)
        entries = payload.get("siteEntry", [])
        if not isinstance(entries, list):
            raise GSCPermanentError("Search Console returned malformed siteEntry data")
        return [entry for entry in entries if isinstance(entry, dict)]

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
                last_error = GSCTransientError(
                    f"Search Console transient HTTP {response.status_code}"
                )
                if attempt == self.max_attempts:
                    break
                self._backoff(attempt)
                continue
            if response.status_code >= 400:
                raise GSCPermanentError(f"Search Console HTTP {response.status_code}")
            return response
        raise GSCTransientError("Search Console request retries exhausted") from last_error

    def _backoff(self, attempt: int) -> None:
        delay = min(30.0, (2 ** (attempt - 1)) + random.uniform(0, 1))
        LOGGER.warning("gsc_retry", extra={"attempt": attempt, "delay_seconds": delay})
        self.sleeper(delay)


class GSCClient:
    def __init__(
        self,
        transport: GSCPageTransport,
        *,
        row_limit: int = 25_000,
        max_pages: int = 100,
    ) -> None:
        if row_limit < 1 or row_limit > 25_000:
            raise ValueError("row_limit must be between 1 and 25000")
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        self.transport = transport
        self.row_limit = row_limit
        self.max_pages = max_pages

    def validate_property(self, property_uri: str) -> None:
        sites = self.transport.list_sites()
        if property_uri not in {entry.get("siteUrl") for entry in sites}:
            raise GSCPermanentError("configured property is not accessible to these credentials")

    def iter_rows(
        self, config: GSCConnectionConfig, start_date: date, end_date: date
    ) -> Iterator[dict[str, Any]]:
        start_row = 0
        for _ in range(self.max_pages):
            body = self._body(config, start_date, end_date, start_row)
            payload = self.transport.query(config.property_uri, body)
            rows = payload.get("rows", [])
            if not isinstance(rows, list):
                raise GSCPermanentError("Search Console returned malformed rows")
            if not rows:
                return
            for row in rows:
                if not isinstance(row, dict):
                    raise GSCPermanentError("Search Console returned a malformed row")
                yield row
            if len(rows) < self.row_limit:
                return
            start_row += len(rows)
        raise GSCTransientError("Search Console pagination safety limit reached")

    def _body(
        self, config: GSCConnectionConfig, start_date: date, end_date: date, start_row: int
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": list(config.dimensions),
            "type": config.search_type,
            "dataState": "final",
            "rowLimit": self.row_limit,
            "startRow": start_row,
        }
        filters = []
        if config.country:
            filters.append(
                {"dimension": "country", "operator": "equals", "expression": config.country}
            )
        if config.device:
            filters.append(
                {"dimension": "device", "operator": "equals", "expression": config.device}
            )
        if filters:
            body["dimensionFilterGroups"] = [{"groupType": "and", "filters": filters}]
        return body


def _json_object(response: Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as error:
        raise GSCPermanentError("Search Console returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise GSCPermanentError("Search Console returned a non-object response")
    return payload
