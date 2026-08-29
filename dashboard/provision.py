#!/usr/bin/env python3
"""Idempotently provision the local GIS Metabase dashboard through its API."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
VARIABLE_PATTERN = re.compile(r"{{\s*([a-z_]+)\s*}}")
DATE_VARIABLES = {"start_date", "end_date"}


class MetabaseAPI:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session_id: str | None = None

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["X-Metabase-Session"] = self.session_id
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read()
        except HTTPError as error:
            detail = error.read().decode(errors="replace")[:500]
            raise RuntimeError(
                f"Metabase API {method} {path} failed: {error.code} {detail}"
            ) from error
        return json.loads(raw) if raw else None

    def wait_until_ready(self, attempts: int = 60) -> None:
        for _ in range(attempts):
            try:
                self.request("GET", "/api/health")
                return
            except (URLError, RuntimeError):
                time.sleep(2)
        raise RuntimeError("Metabase did not become ready")


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


def database_payload() -> dict[str, Any]:
    return {
        "engine": "postgres",
        "name": "GIS Analytics",
        "details": {
            "host": os.environ.get("METABASE_GIS_DB_HOST", "db"),
            "port": int(os.environ.get("METABASE_GIS_DB_PORT", "5432")),
            "dbname": os.environ.get("GIS_DB_NAME", "gis"),
            "user": os.environ.get("GIS_DB_USER", "gis"),
            "password": required_env("GIS_DB_PASSWORD"),
            "ssl": False,
        },
        "is_full_sync": True,
        "is_on_demand": False,
    }


def initialize_or_login(api: MetabaseAPI) -> None:
    email = required_env("METABASE_ADMIN_EMAIL")
    password = required_env("METABASE_ADMIN_PASSWORD")
    properties = api.request("GET", "/api/session/properties")
    setup_token = properties.get("setup-token")
    if setup_token:
        api.request(
            "POST",
            "/api/setup",
            {
                "token": setup_token,
                "user": {
                    "email": email,
                    "password": password,
                    "first_name": os.environ.get("METABASE_ADMIN_FIRST_NAME", "GIS"),
                    "last_name": os.environ.get("METABASE_ADMIN_LAST_NAME", "Operator"),
                    "site_name": "GIS Growth Intelligence",
                },
                "prefs": {"site_name": "GIS Growth Intelligence", "allow_tracking": False},
                "database": database_payload(),
            },
        )
    session = api.request("POST", "/api/session", {"username": email, "password": password})
    api.session_id = session["id"]


def ensure_database(api: MetabaseAPI) -> int:
    databases = api.request("GET", "/api/database").get("data", [])
    existing = next((item for item in databases if item.get("name") == "GIS Analytics"), None)
    if existing:
        return int(existing["id"])
    return int(api.request("POST", "/api/database", database_payload())["id"])


def ensure_collection(api: MetabaseAPI, name: str) -> int:
    existing = next(
        (item for item in api.request("GET", "/api/collection") if item["name"] == name), None
    )
    if existing:
        return int(existing["id"])
    return int(api.request("POST", "/api/collection", {"name": name, "color": "#509EE3"})["id"])


def template_tags(sql: str) -> dict[str, dict[str, Any]]:
    tags: dict[str, dict[str, Any]] = {}
    for name in sorted(set(VARIABLE_PATTERN.findall(sql))):
        tags[name] = {
            "id": name,
            "name": name,
            "display-name": name.replace("_", " ").title(),
            "type": "date" if name in DATE_VARIABLES else "text",
            "required": False,
        }
    return tags


def search(api: MetabaseAPI, model: str, name: str) -> dict[str, Any] | None:
    query = urlencode({"q": name, "models": model})
    results = api.request("GET", f"/api/search?{query}")
    if isinstance(results, dict):
        results = results.get("data", [])
    return next((item for item in results if item.get("name") == name), None)


def ensure_card(
    api: MetabaseAPI, definition: dict[str, Any], database_id: int, collection_id: int
) -> int:
    sql = (ROOT / definition["file"]).read_text()
    payload = {
        "name": definition["name"],
        "description": "Provisioned from dashboard/manifest.json",
        "collection_id": collection_id,
        "display": definition["display"],
        "visualization_settings": definition.get("visualization_settings", {}),
        "dataset_query": {
            "database": database_id,
            "type": "native",
            "native": {"query": sql, "template-tags": template_tags(sql)},
        },
    }
    existing = search(api, "card", definition["name"])
    if existing:
        card_id = int(existing["id"])
        api.request("PUT", f"/api/card/{card_id}", payload)
        return card_id
    return int(api.request("POST", "/api/card", payload)["id"])


def parameter_mappings(card_id: int, sql: str) -> list[dict[str, Any]]:
    dashboard_parameters = {"tenant_id", "site_id", "start_date", "end_date"}
    return [
        {
            "parameter_id": name,
            "card_id": card_id,
            "target": ["variable", ["template-tag", name]],
        }
        for name in sorted(set(VARIABLE_PATTERN.findall(sql)) & dashboard_parameters)
    ]


def ensure_dashboard(
    api: MetabaseAPI,
    manifest: dict[str, Any],
    collection_id: int,
    cards: list[tuple[int, dict[str, Any]]],
) -> int:
    definition = manifest["dashboard"]
    payload = {
        "name": definition["name"],
        "description": definition["description"],
        "collection_id": collection_id,
        "parameters": definition["parameters"],
    }
    existing = search(api, "dashboard", definition["name"])
    if existing:
        dashboard_id = int(existing["id"])
        api.request("PUT", f"/api/dashboard/{dashboard_id}", payload)
    else:
        dashboard_id = int(api.request("POST", "/api/dashboard", payload)["id"])

    details = api.request("GET", f"/api/dashboard/{dashboard_id}")
    attached = {item.get("card_id"): item for item in details.get("dashcards", [])}
    dashcards = []
    for index, (card_id, card) in enumerate(cards, start=1):
        sql = (ROOT / card["file"]).read_text()
        existing_card = attached.get(card_id)
        dashcards.append(
            {
                "id": existing_card["id"] if existing_card else -index,
                "card_id": card_id,
                "row": card["row"],
                "col": card["col"],
                "size_x": card["size_x"],
                "size_y": card["size_y"],
                "visualization_settings": card.get("visualization_settings", {}),
                "parameter_mappings": parameter_mappings(card_id, sql),
                "series": [],
            }
        )
    api.request("PUT", f"/api/dashboard/{dashboard_id}/cards", {"cards": dashcards})
    return dashboard_id


def validate_cards(api: MetabaseAPI, cards: list[tuple[int, dict[str, Any]]]) -> None:
    """Execute every provisioned question once without optional filters."""
    for card_id, card in cards:
        result = api.request("POST", f"/api/card/{card_id}/query", {})
        if not isinstance(result, dict) or "data" not in result:
            raise RuntimeError(f"Metabase did not return query data for {card['name']}")


def main() -> int:
    manifest = json.loads((ROOT / "manifest.json").read_text())
    api = MetabaseAPI(os.environ.get("METABASE_URL", "http://localhost:3030"))
    api.wait_until_ready()
    initialize_or_login(api)
    database_id = ensure_database(api)
    collection_id = ensure_collection(api, manifest["collection"])
    cards = [
        (ensure_card(api, card, database_id, collection_id), card) for card in manifest["cards"]
    ]
    dashboard_id = ensure_dashboard(api, manifest, collection_id, cards)
    validate_cards(api, cards)
    print(f"Provisioned Growth Dashboard — P0 (dashboard id {dashboard_id})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, URLError) as error:
        print(f"Provisioning failed: {error}", file=sys.stderr)
        sys.exit(1)
