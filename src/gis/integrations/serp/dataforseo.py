from __future__ import annotations

from typing import Any

import requests

from gis.models import TrackedQuery

API_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"


class DataForSEOProvider:
    def __init__(
        self, login: str, password: str, *, session: requests.Session | None = None
    ) -> None:
        self.login, self.password, self.session = login, password, session or requests.Session()

    def request_body(self, query: TrackedQuery) -> list[dict[str, Any]]:
        body: dict[str, Any] = {
            "keyword": query.query_text,
            "language_code": query.language_code,
            "device": query.device,
            "depth": query.requested_depth,
        }
        if query.location_code is not None:
            body["location_code"] = query.location_code
        elif query.location_name:
            body["location_name"] = query.location_name
        return [body]

    def collect(self, query: TrackedQuery) -> dict[str, Any]:
        response = self.session.post(
            API_URL, json=self.request_body(query), auth=(self.login, self.password), timeout=60
        )
        if response.status_code >= 400:
            raise RuntimeError(f"DataForSEO HTTP {response.status_code}")
        value = response.json()
        if not isinstance(value, dict):
            raise RuntimeError("DataForSEO returned malformed JSON")
        return value
