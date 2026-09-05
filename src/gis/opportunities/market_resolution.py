"""Deterministic, provenance-preserving market-concept resolution."""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import CollectionTarget, CollectionTargetEvidence, CollectionTargetType

METHOD_VERSION = "MARKET_CONCEPT_RESOLVER_V1"
YEARS = re.compile(r"\b(?:19|20)\d{2}\b")
NON_QUERY = re.compile(r"(^[\"']|[\"']$|\.(?:zip|csv|json|xml|pdf)$|[/\\])", re.I)
SPELLING = {
    "cal": "calculator",
    "calc": "calculator",
    "caculator": "calculator",
    "calcuator": "calculator",
    "calcukator": "calculator",
    "calculater": "calculator",
    "calcultor": "calculator",
    "calcutor": "calculator",
    "calvulator": "calculator",
    "claculator": "calculator",
    "mha": "bah",
    "housing allowance": "bah",
    "basic allowance for housing": "bah",
    "debt to income": "dti",
}
SERVICES = {"army", "navy", "marines", "usmc", "air force", "coast guard", "national guard"}
GEO = {
    "virginia",
    "texas",
    "florida",
    "alaska",
    "california",
    "washington",
    "state",
    "zip",
    "code",
    "beach",
    "austin",
    "pentagon",
}

INTENTS: list[tuple[str, tuple[str, ...], str, str]] = [
    ("VA_CLOSING_COSTS", ("closing cost",), "VA Loan Costs", "Estimate VA closing costs"),
    ("VA_FUNDING_FEE", ("funding fee",), "VA Loan Costs", "Calculate VA funding fee"),
    ("VA_RESIDUAL_INCOME", ("residual income",), "VA Qualification", "Evaluate residual income"),
    (
        "VA_ENTITLEMENT",
        ("entitlement", "guaranty amount"),
        "VA Eligibility",
        "Evaluate VA entitlement",
    ),
    (
        "VA_AFFORDABILITY",
        ("afford", "affordability"),
        "VA Affordability",
        "Calculate VA affordability",
    ),
    ("VA_DTI", (" dti ", "dti", "debt to income"), "VA Qualification", "Evaluate debt-to-income"),
    (
        "VA_LOAN_PAYMENT",
        ("va loan", "va mortgage", "veteran home loan"),
        "VA Loan Calculators",
        "Calculate VA loan payment",
    ),
    ("BAH_LOOKUP", ("bah",), "Military Housing Allowance", "Calculate or look up BAH"),
]


def normalize_query(value: str) -> dict[str, Any]:
    raw = value.strip()
    artifact = bool(NON_QUERY.search(raw))
    text = raw.casefold().strip(" \"'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    collapsed = re.sub(r"\s+", " ", text).strip()
    text = f" {collapsed} "
    for source, target in sorted(SPELLING.items(), key=lambda item: -len(item[0])):
        text = text.replace(f" {source} ", f" {target} ")
    text = re.sub(r"\s+", " ", text).strip()
    years = YEARS.findall(text)
    services = sorted(item for item in SERVICES if item in text)
    geography = sorted(item for item in GEO if re.search(rf"\b{re.escape(item)}\b", text))
    return {
        "raw": value,
        "normalized": text,
        "classification": "SOURCE_ARTIFACT" if artifact else "VALID_QUERY",
        "year_modifiers": years,
        "service_modifiers": services,
        "geographic_modifiers": geography,
        "method": METHOD_VERSION,
    }


def resolve_query(value: str) -> dict[str, Any]:
    result = normalize_query(value)
    if result["classification"] != "VALID_QUERY" or not result["normalized"]:
        return {
            **result,
            "concept_key": None,
            "concept": None,
            "topic": None,
            "intent": "UNRESOLVED",
        }
    padded = f" {result['normalized']} "
    for key, needles, topic, intent in INTENTS:
        if any(needle in padded for needle in needles):
            variant = (
                "CALCULATION"
                if any(x in padded for x in ("calculator", "estimate", "lookup"))
                else "INFORMATIONAL"
            )
            return {
                **result,
                "concept_key": key,
                "concept": intent,
                "topic": topic,
                "intent": variant,
            }
    return {
        **result,
        "concept_key": None,
        "concept": None,
        "topic": None,
        "intent": "UNRESOLVED",
        "classification": "UNRESOLVED",
    }


def resolve_portfolio(session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
    targets = list(
        session.scalars(
            select(CollectionTarget).where(
                CollectionTarget.tenant_id == tenant_id, CollectionTarget.site_id == site_id
            )
        )
    )
    query_targets = [row for row in targets if row.target_type is CollectionTargetType.QUERY]
    evidence = defaultdict(list)
    if query_targets:
        for evidence_row in session.scalars(
            select(CollectionTargetEvidence).where(
                CollectionTargetEvidence.target_id.in_([t.id for t in query_targets])
            )
        ):
            evidence[evidence_row.target_id].append(
                {
                    "id": str(evidence_row.id),
                    "source": evidence_row.source_system,
                    "type": evidence_row.evidence_type,
                    "observed_at": evidence_row.evidence_at.isoformat(),
                }
            )
    concepts: dict[str, dict[str, Any]] = {}
    classifications: Counter[str] = Counter()
    normalized: set[str] = set()
    raw_items = []
    for target in query_targets:
        resolved = resolve_query(target.display_value)
        normalized.add(resolved["normalized"])
        classifications[resolved["classification"]] += 1
        item = {
            **resolved,
            "target_id": str(target.id),
            "target_href": f"/collection/{target.id}",
            "sources": sorted({x["source"] for x in evidence[target.id]}),
            "provenance": evidence[target.id],
        }
        raw_items.append(item)
        if resolved["concept_key"]:
            concept = concepts.setdefault(
                resolved["concept_key"],
                {
                    "key": resolved["concept_key"],
                    "name": resolved["concept"],
                    "topic": resolved["topic"],
                    "raw_queries": [],
                    "variants": Counter(),
                    "sources": set(),
                },
            )
            concept["raw_queries"].append(item)
            concept["variants"][resolved["intent"]] += 1
            concept["sources"].update(item["sources"])
    concept_items = []
    for concept_row in concepts.values():
        concept_items.append(
            {
                **concept_row,
                "raw_query_count": len(concept_row["raw_queries"]),
                "variants": dict(concept_row["variants"]),
                "sources": sorted(concept_row["sources"]),
            }
        )
    return {
        "method_version": METHOD_VERSION,
        "raw_targets": len(targets),
        "raw_query_targets": len(query_targets),
        "canonical_normalized_queries": len(normalized),
        "canonical_market_concepts": len(concept_items),
        "topic_clusters": len({x["topic"] for x in concept_items}),
        "classification_counts": dict(classifications),
        "concepts": sorted(concept_items, key=lambda x: (-x["raw_query_count"], x["name"])),
        "raw_queries": raw_items,
        "semantics": "Derived read model only. Raw targets and evidence remain authoritative and unchanged.",
    }


def resolve_coverage(concept_key: str | None, assets: Iterable[dict[str, Any]]) -> dict[str, Any]:
    if not concept_key:
        return {
            "state": "UNKNOWN",
            "method": METHOD_VERSION,
            "matches": [],
            "reason": "No canonical concept was resolved.",
        }
    matches = [a for a in assets if concept_key in set(a.get("concept_keys", []))]
    if not matches:
        return {
            "state": "UNKNOWN",
            "method": METHOD_VERSION,
            "matches": [],
            "reason": "No governed asset-to-concept assertion exists; missing evidence is not NO_COVERAGE.",
        }
    return {
        "state": "COVERED" if any(a.get("active", True) for a in matches) else "NO_COVERAGE",
        "method": METHOD_VERSION,
        "matches": matches,
        "reason": "Deterministic asset-to-concept assertion.",
    }
