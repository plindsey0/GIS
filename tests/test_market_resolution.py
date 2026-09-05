from __future__ import annotations

from gis.opportunities.market_resolution import normalize_query, resolve_coverage, resolve_query


def test_normalization_preserves_raw_and_resolves_spelling_and_modifiers() -> None:
    row = resolve_query("Army BAH Calcukator 2026")
    assert row["raw"] == "Army BAH Calcukator 2026"
    assert row["normalized"] == "army bah calculator 2026"
    assert row["concept_key"] == "BAH_LOOKUP"
    assert row["year_modifiers"] == ["2026"]
    assert row["service_modifiers"] == ["army"]


def test_meaningful_intents_are_not_collapsed() -> None:
    affordability = resolve_query("VA loan affordability calculator")
    closing = resolve_query("VA loan closing cost calculator")
    assert affordability["concept_key"] == "VA_AFFORDABILITY"
    assert closing["concept_key"] == "VA_CLOSING_COSTS"
    assert affordability["concept_key"] != closing["concept_key"]


def test_geographic_variant_remains_explicit() -> None:
    row = resolve_query("BAH by zip code")
    assert row["concept_key"] == "BAH_LOOKUP"
    assert {"zip", "code"}.issubset(row["geographic_modifiers"])


def test_artifact_is_classified_without_deleting_raw_value() -> None:
    row = normalize_query('"bah-ascii-2026.zip"')
    assert row["classification"] == "SOURCE_ARTIFACT"
    assert row["raw"] == '"bah-ascii-2026.zip"'


def test_coverage_unknown_is_not_no_coverage() -> None:
    unknown = resolve_coverage("VA_RESIDUAL_INCOME", [])
    assert unknown["state"] == "UNKNOWN"
    covered = resolve_coverage(
        "VA_RESIDUAL_INCOME",
        [{"id": "asset-1", "concept_keys": ["VA_RESIDUAL_INCOME"], "active": True}],
    )
    assert covered["state"] == "COVERED"
