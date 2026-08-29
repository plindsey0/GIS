from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
DASHBOARD = ROOT / "dashboard"


def _manifest() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((DASHBOARD / "manifest.json").read_text()))


def test_dashboard_has_all_p0_sections_and_reproducible_queries() -> None:
    manifest = _manifest()
    expected = {
        "A · Executive Overview",
        "B · Search Performance",
        "C · Page Performance",
        "D · Keyword / Query Performance",
        "E · Acquisition",
        "F · Calculator Performance",
        "G · Conversion Performance",
        "H · Data Quality / Reconciliation",
    }
    assert {card["name"] for card in manifest["cards"]}.issuperset(expected)
    for card in manifest["cards"]:
        query = (DASHBOARD / card["file"]).read_text()
        assert "tenant_id" in query
        assert "site_id" in query
        assert "start_date" in query
        assert "end_date" in query
        assert "vahomemath" not in query.lower()


def test_dashboard_global_filters_are_mapped_by_provisioner() -> None:
    spec = importlib.util.spec_from_file_location("dashboard_provision", DASHBOARD / "provision.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tags = module.template_tags("select {{tenant_id}}, {{start_date}}, {{query}}")
    assert tags["tenant_id"]["type"] == "text"
    assert tags["start_date"]["type"] == "date"
    assert tags["query"]["type"] == "text"
    mappings = module.parameter_mappings(7, "{{tenant_id}} {{site_id}} {{start_date}} {{page}}")
    assert {mapping["parameter_id"] for mapping in mappings} == {
        "tenant_id",
        "site_id",
        "start_date",
    }
