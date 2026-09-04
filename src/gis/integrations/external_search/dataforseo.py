from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import requests

from gis.models import FailureCategory
from gis.orchestration.reliability import ClassifiedFailure

RANKED_KEYWORDS_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live"
COMPETITORS_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/competitors_domain/live"
SUCCESS_STATUS = 20000


class ExternalSearchProviderError(ClassifiedFailure):
    def __init__(
        self,
        message: str,
        category: FailureCategory = FailureCategory.UNKNOWN_TERMINAL,
        *,
        cost: Decimal | None = None,
    ):
        super().__init__(category, message)
        self.cost = cost


@dataclass(frozen=True)
class SearchRequest:
    observation_type: str
    target_domain: str
    location_code: int | None = None
    location_name: str | None = None
    country_code: str | None = None
    language_code: str = "en"
    device: str | None = None
    limit: int = 100


@dataclass(frozen=True)
class ProviderCollection:
    task_id: str | None
    observed_at: datetime
    cost: Decimal | None
    items: list[dict[str, Any]]
    metadata: dict[str, Any]


def normalize_domain(value: str) -> str:
    candidate = value.strip().lower()
    candidate = re.sub(r"^https?://", "", candidate).split("/", 1)[0].split(":", 1)[0]
    candidate = candidate.removeprefix("www.").rstrip(".")
    if not candidate or len(candidate) > 253 or "." not in candidate:
        raise ValueError("target must be a valid domain")
    return candidate.encode("idna").decode("ascii")


class DataForSEOExternalSearchProvider:
    def __init__(
        self, login: str, password: str, *, session: requests.Session | None = None
    ) -> None:
        self.login, self.password, self.session = login, password, session or requests.Session()

    @staticmethod
    def request_body(request: SearchRequest) -> list[dict[str, Any]]:
        if request.observation_type not in {"ranked_keywords", "competitors"}:
            raise ValueError("unsupported external-search observation type")
        if not 1 <= request.limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if request.location_code is not None and request.location_name:
            raise ValueError("location_code and location_name are mutually exclusive")
        if request.location_code is None and not request.location_name:
            raise ValueError("DataForSEO Labs requires a location target")
        if not re.fullmatch(r"[a-z]{2}", request.language_code.lower()):
            raise ValueError("language_code must be a two-letter code")
        body: dict[str, Any] = {
            "target": normalize_domain(request.target_domain),
            "language_code": request.language_code.lower(),
            "limit": request.limit,
        }
        if request.location_code is not None:
            body["location_code"] = request.location_code
        else:
            body["location_name"] = request.location_name
        if request.observation_type == "ranked_keywords":
            body["item_types"] = ["organic", "featured_snippet", "local_pack"]
        else:
            body["exclude_top_domains"] = True
        return [body]

    def collect(self, request: SearchRequest) -> ProviderCollection:
        url = (
            RANKED_KEYWORDS_URL
            if request.observation_type == "ranked_keywords"
            else COMPETITORS_URL
        )
        body = self.request_body(request)
        try:
            response = self.session.post(
                url, json=body, auth=(self.login, self.password), timeout=60
            )
        except requests.RequestException as error:
            raise ExternalSearchProviderError(
                f"DataForSEO transport failed: {type(error).__name__}",
                FailureCategory.TRANSIENT_NETWORK,
            ) from error
        if response.status_code >= 400:
            category = {
                401: FailureCategory.AUTHENTICATION_FAILED,
                403: FailureCategory.AUTHORIZATION_FAILED,
                429: FailureCategory.PROVIDER_429,
            }.get(
                response.status_code,
                FailureCategory.PROVIDER_5XX
                if response.status_code >= 500
                else FailureCategory.INVALID_REQUEST,
            )
            raise ExternalSearchProviderError(f"DataForSEO HTTP {response.status_code}", category)
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise ExternalSearchProviderError("DataForSEO returned invalid JSON") from error
        if not isinstance(payload, dict) or payload.get("status_code") != SUCCESS_STATUS:
            raise ExternalSearchProviderError("DataForSEO request failed")
        tasks = payload.get("tasks")
        if not isinstance(tasks, list) or not tasks or not isinstance(tasks[0], dict):
            raise ExternalSearchProviderError("DataForSEO response contains no task")
        task = tasks[0]
        task_cost = Decimal(str(task["cost"])) if task.get("cost") is not None else None
        if task.get("status_code") != SUCCESS_STATUS:
            code = task.get("status_code")
            category = (
                FailureCategory.AUTHENTICATION_FAILED
                if code == 40100
                else FailureCategory.BUDGET_BLOCKED
                if code == 40200
                else FailureCategory.INVALID_REQUEST
            )
            raise ExternalSearchProviderError(
                f"DataForSEO task failed: {code}", category, cost=task_cost
            )
        results = task.get("result")
        if not isinstance(results, list) or not results or not isinstance(results[0], dict):
            raise ExternalSearchProviderError("DataForSEO task contains no result", cost=task_cost)
        result = results[0]
        items = result.get("items", [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ExternalSearchProviderError(
                "DataForSEO result items are malformed", cost=task_cost
            )
        raw_time = result.get("datetime")
        try:
            observed_at = (
                datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                if raw_time
                else datetime.now(timezone.utc)
            )
        except ValueError as error:
            raise ExternalSearchProviderError(
                "DataForSEO result datetime is malformed", cost=task_cost
            ) from error
        return ProviderCollection(
            task_id=str(task["id"]) if task.get("id") else None,
            observed_at=observed_at,
            cost=task_cost,
            items=items,
            metadata={
                "total_count": result.get("total_count"),
                "endpoint": request.observation_type,
            },
        )
