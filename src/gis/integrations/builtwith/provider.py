from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from gis.integrations.external_search.dataforseo import normalize_domain
from gis.models import FailureCategory
from gis.orchestration.reliability import ClassifiedFailure

ENDPOINT = "https://api.builtwith.com/v23/api.json"


@dataclass(frozen=True)
class Profile:
    domain: str
    payload: dict[str, Any]
    technologies: list[dict[str, Any]]
    headers: dict[str, str]


def parse_profile(payload: Any, domain: str, headers: dict[str, str] | None = None) -> Profile:
    """Validate the full single-domain response before persisting any detections."""
    if not isinstance(payload, dict):
        raise ClassifiedFailure(FailureCategory.UNKNOWN_TERMINAL, "Malformed BuiltWith response")
    errors = payload.get("Errors") or []
    if errors:
        codes = (
            {str(e.get("Code")) for e in errors if isinstance(e, dict)}
            if isinstance(errors, list)
            else set()
        )
        category = (
            FailureCategory.AUTHENTICATION_FAILED
            if "-2" in codes
            else FailureCategory.BUDGET_BLOCKED
            if codes & {"-3", "-5"}
            else FailureCategory.PROVIDER_5XX
            if "-99" in codes
            else FailureCategory.INVALID_REQUEST
        )
        raise ClassifiedFailure(category, "BuiltWith rejected the domain lookup")
    results = payload.get("Results")
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise ClassifiedFailure(FailureCategory.UNKNOWN_TERMINAL, "Malformed BuiltWith results")
    result = results[0]
    lookup = result.get("Lookup")
    if not isinstance(lookup, str) or lookup.lower().rstrip(".") != domain:
        raise ClassifiedFailure(
            FailureCategory.UNKNOWN_TERMINAL, "BuiltWith returned a different domain"
        )
    detail = result.get("Result")
    paths = detail.get("Paths") if isinstance(detail, dict) else None
    if not isinstance(paths, list):
        raise ClassifiedFailure(FailureCategory.UNKNOWN_TERMINAL, "Malformed BuiltWith paths")
    technologies = []
    for path in paths:
        if not isinstance(path, dict) or not isinstance(path.get("Technologies"), list):
            raise ClassifiedFailure(
                FailureCategory.UNKNOWN_TERMINAL, "Malformed BuiltWith technology list"
            )
        for technology in path["Technologies"]:
            if (
                not isinstance(technology, dict)
                or not isinstance(technology.get("Name"), str)
                or not technology["Name"].strip()
            ):
                raise ClassifiedFailure(
                    FailureCategory.UNKNOWN_TERMINAL, "Malformed BuiltWith technology"
                )
            technologies.append(
                {
                    "technology": technology,
                    "path": {k: v for k, v in path.items() if k != "Technologies"},
                }
            )
    return Profile(domain, payload, technologies, headers or {})


class BuiltWithProvider:
    def __init__(self, api_key: str, *, session: requests.Session | None = None):
        self.api_key = api_key
        self.session = session or requests.Session()

    def collect(self, domain: str) -> Profile:
        domain = normalize_domain(domain)
        try:
            response = self.session.get(
                ENDPOINT,
                params={"LOOKUP": domain, "NOMETA": "yes", "NOPII": "yes", "NOATTR": "yes"},
                headers={"Authorization": f"API {self.api_key}"},
                timeout=60,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise ClassifiedFailure(
                FailureCategory.TRANSIENT_NETWORK,
                "BuiltWith transport failed; charge outcome unknown",
            ) from None
        code = response.status_code
        if code != 200:
            category = (
                FailureCategory.AUTHENTICATION_FAILED
                if code == 401
                else FailureCategory.AUTHORIZATION_FAILED
                if code == 403
                else FailureCategory.PROVIDER_429
                if code == 429
                else FailureCategory.PROVIDER_5XX
                if code >= 500
                else FailureCategory.INVALID_REQUEST
            )
            raise ClassifiedFailure(category, f"BuiltWith HTTP {code}")
        try:
            payload = json.loads(response.text, parse_float=str)
        except (ValueError, TypeError):
            raise ClassifiedFailure(
                FailureCategory.UNKNOWN_TERMINAL, "Malformed BuiltWith JSON"
            ) from None
        # Only documented telemetry headers are retained; never request URLs or credentials.
        headers = {
            k.lower(): v
            for k, v in response.headers.items()
            if k.lower().startswith(("x-api-credits-", "x-ratelimit-"))
        }
        return parse_profile(payload, domain, headers)
