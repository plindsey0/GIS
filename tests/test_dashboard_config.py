from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).parents[1]
DASHBOARD = ROOT / "dashboard"


def _manifest() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((DASHBOARD / "manifest.json").read_text()))


def _module() -> Any:
    spec = importlib.util.spec_from_file_location("dashboard_provision", DASHBOARD / "provision.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_executive_information_architecture_is_reproducible() -> None:
    manifest = _manifest()
    assert manifest["dashboards"][0]["name"] == "GIS Executive Intelligence"
    collections = {item["name"] for item in manifest["collections"]}
    assert {
        "Executive",
        "Growth Performance",
        "Search Intelligence",
        "Competitive Intelligence",
        "Operations",
        "Governance",
        "Cost",
        "Diagnostics",
    } <= collections
    primary_names = {card["name"] for card in manifest["dashboards"][0]["cards"]}
    assert any("Growth performance" in name for name in primary_names)
    assert any("Competitive position" in name for name in primary_names)
    assert any("Capability coverage" in name for name in primary_names)
    assert any("Future intelligence" in name for name in primary_names)
    for dashboard in manifest["dashboards"]:
        for card in dashboard["cards"]:
            query = (DASHBOARD / card["file"]).read_text()
            assert all(name in query for name in ("tenant_id", "site_id", "start_date", "end_date"))
            assert "vahomemath" not in query.lower()


def test_global_filters_are_mapped() -> None:
    module = _module()
    tags = module.template_tags("select {{tenant_id}}, {{start_date}}, {{query}}")
    assert tags["tenant_id"]["type"] == "text"
    assert tags["start_date"]["type"] == "date"
    mappings = module.parameter_mappings(7, "{{tenant_id}} {{site_id}} {{start_date}} {{page}}")
    assert {mapping["parameter_id"] for mapping in mappings} == {
        "tenant_id",
        "site_id",
        "start_date",
    }


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"implemented": False}, "NOT_IMPLEMENTED"),
        ({"implemented": True, "rights_blocked": True}, "BLOCKED_BY_RIGHTS"),
        ({"implemented": True, "latest_run_status": "FAILED"}, "FAILED"),
        ({"implemented": True, "evidence_count": 2, "open_alerts": 1}, "DEGRADED"),
        ({"implemented": True, "evidence_count": 2, "stale": True}, "STALE"),
        ({"implemented": True, "all_schedules_disabled": True}, "DISABLED"),
        ({"implemented": True}, "IMPLEMENTED_NO_DATA"),
        ({"implemented": True, "connection_exists": True}, "CONFIGURED"),
        ({"implemented": True, "evidence_count": 2}, "OPERATIONAL"),
    ],
)
def test_capability_status_precedence(kwargs: dict[str, Any], expected: str) -> None:
    assert _module().derive_capability_status(**kwargs) == expected


def test_no_data_zero_cost_and_semantic_safety_contracts() -> None:
    sql = "\n".join(path.read_text() for path in (DASHBOARD / "questions/executive").glob("*.sql"))
    assert "cost_semantics" in sql
    assert "data_availability" in sql
    assert "OBSERVED_DIFFERENCE_NOT_RECOMMENDATION" in sql
    assert "provider_metrics" in sql
    events = (DASHBOARD / "questions/executive/recent_events.sql").read_text()
    assert "semantic_class" in events and "confidence" in events


def test_collection_hierarchy_is_deterministic() -> None:
    module = _module()

    class FakeAPI:
        def __init__(self) -> None:
            self.collections: list[dict[str, Any]] = []

        def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
            if method == "GET":
                return self.collections
            assert payload is not None
            if method == "POST":
                item = {**payload, "id": len(self.collections) + 1}
                self.collections.append(item)
                return item
            collection_id = int(path.rsplit("/", 1)[-1])
            self.collections[collection_id - 1].update(payload)
            return self.collections[collection_id - 1]

    api = FakeAPI()
    first = module.ensure_collections(api, _manifest()["collections"])
    second = module.ensure_collections(api, _manifest()["collections"])
    assert first == second
    assert len(api.collections) == len(_manifest()["collections"])
    assert api.collections[first["Executive"] - 1]["parent_id"] == first["GIS"]
