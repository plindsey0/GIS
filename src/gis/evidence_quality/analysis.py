from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import tldextract

from gis.models import (
    CorroborationState,
    DemandEvidenceStrength,
    EvidenceCompatibility,
    QualityDimensionState,
    ResolutionStrength,
    SourceIndependenceState,
)

METHOD_VERSION = "EVIDENCE_QUALITY_V1"
DOMAIN_METHOD = "DOMAIN_NORMALIZATION_V1"
REGISTRABLE_METHOD = "REGISTRABLE_DOMAIN_V1"
URL_METHOD = "URL_NORMALIZATION_V1"
QUERY_METHOD = "QUERY_NORMALIZATION_V1"
TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
}
_extract = tldextract.TLDExtract(suffix_list_urls=())


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class DomainIdentity:
    hostname: str
    registrable_domain: str
    subdomain: str


def normalize_domain(value: str) -> DomainIdentity:
    raw = value.strip().rstrip(".")
    if "://" in raw:
        raw = urlsplit(raw).hostname or ""
    raw = raw.split("/", 1)[0].split(":", 1)[0].rstrip(".")
    hostname = raw.casefold().encode("idna").decode("ascii")
    if hostname.startswith("www."):
        hostname = hostname[4:]
    result = _extract(hostname)
    registrable = ".".join(part for part in (result.domain, result.suffix) if part)
    return DomainIdentity(hostname, registrable or hostname, result.subdomain)


def normalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.casefold() or "https"
    host = normalize_domain(parsed.hostname or "").hostname
    port = parsed.port
    netloc = (
        host
        if port is None or (scheme, port) in {("http", 80), ("https", 443)}
        else f"{host}:{port}"
    )
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_PARAMETERS
        )
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_query(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def compatibility(left: dict[str, object], right: dict[str, object]) -> EvidenceCompatibility:
    required = ("entity_key", "metric", "unit", "market_version")
    if any(left.get(key) is None or right.get(key) is None for key in required):
        return EvidenceCompatibility.UNKNOWN
    if any(left[key] != right[key] for key in required):
        return EvidenceCompatibility.INCOMPATIBLE
    scope = ("country", "language", "device", "resolution_days")
    differences = [key for key in scope if left.get(key) != right.get(key)]
    return (
        EvidenceCompatibility.PARTIALLY_COMPATIBLE
        if differences
        else EvidenceCompatibility.COMPATIBLE
    )


def independence(root_sources: Sequence[str | None]) -> tuple[SourceIndependenceState, int]:
    if not root_sources or all(source is None for source in root_sources):
        return SourceIndependenceState.UNKNOWN, 0
    roots = {source for source in root_sources if source}
    if len(roots) == 1:
        return SourceIndependenceState.SAME_ROOT_SOURCE, 1
    if len(roots) < len([source for source in root_sources if source]):
        return SourceIndependenceState.PARTIALLY_INDEPENDENT, len(roots)
    return SourceIndependenceState.INDEPENDENT, len(roots)


def corroboration(
    independent_sources: int, conflict_count: int, evidence_count: int
) -> CorroborationState:
    if conflict_count:
        return CorroborationState.CONFLICTING
    if evidence_count == 0:
        return CorroborationState.INSUFFICIENT
    if independent_sources <= 1:
        return CorroborationState.SINGLE_SOURCE
    if independent_sources == 2:
        return CorroborationState.CORROBORATED
    return CorroborationState.MULTI_SOURCE_CORROBORATED


def sufficiency(
    *,
    identity: ResolutionStrength,
    completeness: QualityDimensionState,
    continuity: QualityDimensionState,
    rights: QualityDimensionState,
    conflict_count: int,
    independent_sources: int,
) -> DemandEvidenceStrength:
    if identity in {ResolutionStrength.UNRESOLVED, ResolutionStrength.CONFLICTING}:
        return DemandEvidenceStrength.INSUFFICIENT
    if rights is QualityDimensionState.BLOCKED or conflict_count:
        return DemandEvidenceStrength.INSUFFICIENT
    if completeness in {
        QualityDimensionState.UNKNOWN,
        QualityDimensionState.LIMITED,
    } or continuity in {
        QualityDimensionState.UNKNOWN,
        QualityDimensionState.LIMITED,
    }:
        return DemandEvidenceStrength.LIMITED
    if independent_sources >= 2:
        return DemandEvidenceStrength.STRONGLY_SUPPORTED
    return DemandEvidenceStrength.SUPPORTED


def ratio_state(observed: Decimal | None, expected: Decimal | None) -> QualityDimensionState:
    if observed is None or expected is None or expected <= 0:
        return QualityDimensionState.UNKNOWN
    ratio = observed / expected
    if ratio >= Decimal("0.9"):
        return QualityDimensionState.STRONG
    if ratio >= Decimal("0.6"):
        return QualityDimensionState.SUPPORTED
    return QualityDimensionState.LIMITED
