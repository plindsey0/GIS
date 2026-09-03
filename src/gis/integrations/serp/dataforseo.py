from __future__ import annotations

import json
import re
from typing import Any

import requests

from gis.models import TrackedQuery

API_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
SUCCESS_STATUS = 20000
COUNTRY_LOCATION_CODES = {"US": 2840}
SUPPORTED_DEVICES = {"desktop", "mobile"}


class SerpProviderError(RuntimeError):
    """Safe provider failure suitable for persistence and operator output."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DataForSEORequestError(SerpProviderError):
    pass


class DataForSEOResponseError(SerpProviderError):
    pass


def _safe_message(value: object) -> str:
    text = re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()
    text = re.sub(r"(?i)(authorization|password|login)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    return text[:500] or "unspecified provider error"


class DataForSEOProvider:
    def __init__(
        self, login: str, password: str, *, session: requests.Session | None = None
    ) -> None:
        self.login, self.password, self.session = login, password, session or requests.Session()

    def request_body(self, query: TrackedQuery) -> list[dict[str, Any]]:
        keyword = query.query_text.strip()
        if not keyword:
            raise DataForSEORequestError("keyword must not be empty")
        language = (query.language_code or "").strip().lower()
        if not re.fullmatch(r"[a-z]{2}", language):
            raise DataForSEORequestError("language_code must be a two-letter code")
        device = (query.device or "").strip().lower()
        if device not in SUPPORTED_DEVICES:
            raise DataForSEORequestError(f"unsupported device: {_safe_message(device)}")
        depth = query.requested_depth
        if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= 200:
            raise DataForSEORequestError("depth must be between 1 and 200")
        if query.location_code is not None and query.location_name:
            raise DataForSEORequestError("location_code and location_name are mutually exclusive")
        body: dict[str, Any] = {
            "keyword": keyword,
            "language_code": language,
            "device": device,
            "depth": depth,
        }
        if query.location_code is not None:
            if query.location_code <= 0:
                raise DataForSEORequestError("location_code must be positive")
            body["location_code"] = query.location_code
        elif query.location_name:
            body["location_name"] = query.location_name.strip()
        else:
            country_code = (query.country_code or "").strip().upper()
            location_code = COUNTRY_LOCATION_CODES.get(country_code)
            if location_code is None:
                raise DataForSEORequestError(
                    f"country_code has no configured DataForSEO location: {_safe_message(country_code)}"
                )
            body["location_code"] = location_code
        return [body]

    def collect(self, query: TrackedQuery) -> dict[str, Any]:
        request_body = self.request_body(query)
        try:
            response = self.session.post(
                API_URL, json=request_body, auth=(self.login, self.password), timeout=60
            )
        except requests.RequestException as error:
            raise DataForSEOResponseError(f"transport failed: {type(error).__name__}") from error
        try:
            payload = response.json()
        except (ValueError, TypeError):
            if response.status_code >= 400:
                raise DataForSEOResponseError(f"HTTP {response.status_code}")
            raise DataForSEOResponseError("response was not valid JSON")
        if response.status_code >= 400:
            message = payload.get("status_message") if isinstance(payload, dict) else None
            detail = f": {_safe_message(message)}" if message else ""
            raise DataForSEOResponseError(f"HTTP {response.status_code}{detail}")
        if not isinstance(payload, dict):
            raise DataForSEOResponseError("response JSON must be an object")
        # Preserve the provider's monetary decimal lexeme before JSON float rounding.
        # Other response metrics retain their existing representation.
        raw_text = getattr(response, "text", None)
        if isinstance(raw_text, str) and raw_text:
            exact_payload = json.loads(raw_text, parse_float=str)
            exact_tasks = exact_payload.get("tasks", []) if isinstance(exact_payload, dict) else []
            parsed_tasks = payload.get("tasks")
            task_pairs = (
                zip(parsed_tasks, exact_tasks)
                if (isinstance(parsed_tasks, list) and isinstance(exact_tasks, list))
                else []
            )
            for task, exact_task in task_pairs:
                if isinstance(task, dict) and isinstance(exact_task, dict) and "cost" in exact_task:
                    task["cost"] = exact_task["cost"]
        top_status = payload.get("status_code")
        if not isinstance(top_status, int):
            raise DataForSEOResponseError("response is missing top-level status_code")
        if top_status != SUCCESS_STATUS:
            raise DataForSEOResponseError(
                f"request failed: {top_status} {_safe_message(payload.get('status_message'))}",
                status_code=top_status,
            )
        tasks = payload.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise DataForSEOResponseError("response contains no tasks")
        task = tasks[0]
        if not isinstance(task, dict):
            raise DataForSEOResponseError("task must be an object")
        task_status = task.get("status_code")
        if not isinstance(task_status, int):
            raise DataForSEOResponseError("task is missing status_code")
        if task_status != SUCCESS_STATUS:
            raise DataForSEOResponseError(
                f"task failed: {task_status} {_safe_message(task.get('status_message'))}",
                status_code=task_status,
            )
        result = task.get("result")
        if result is None:
            raise DataForSEOResponseError("successful task returned null result")
        if not isinstance(result, list):
            raise DataForSEOResponseError("task result must be an array")
        if any(not isinstance(item, dict) for item in result):
            raise DataForSEOResponseError("task result contains a malformed object")
        return payload
