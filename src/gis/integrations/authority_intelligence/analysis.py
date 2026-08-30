from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from urllib.parse import urlsplit

from gis.integrations.content_intelligence.extraction import normalize_url
from gis.models import AnchorClassification, AuthorityFollowState, AuthorityLinkType

GENERIC_ANCHORS = {"click here", "learn more", "read more", "website", "here", "source"}
ANCHOR_METHOD = "deterministic_anchor_classifier"
ANCHOR_VERSION = "1.0.0"


def normalize_domain(value: str) -> str:
    candidate = value if "://" in value else f"https://{value}"
    return normalize_url(candidate)[1]


def canonical_url(value: str) -> tuple[str, str]:
    normalized, domain, _ = normalize_url(value)
    return normalized, domain


def link_identity(
    provider_record_id: str | None, source_url: str, target_url: str, link_type: str
) -> str:
    payload = provider_record_id or "|".join((source_url, target_url, link_type))
    return hashlib.sha256(payload.encode()).hexdigest()


def classify_anchor(
    anchor: str | None, target_domain: str, target_url: str
) -> tuple[AnchorClassification, Decimal]:
    value = re.sub(r"\s+", " ", (anchor or "").strip().casefold())
    if not value:
        return AnchorClassification.IMAGE_OR_EMPTY, Decimal("1")
    if value in GENERIC_ANCHORS:
        return AnchorClassification.GENERIC, Decimal("0.95")
    if value.startswith(("http://", "https://", "www.")):
        return AnchorClassification.URL, Decimal("1")
    brand = target_domain.split(".", 1)[0].replace("-", " ")
    if brand and brand in value:
        return AnchorClassification.BRAND, Decimal("0.85")
    path_terms = {
        term
        for term in re.split(r"[^a-z0-9]+", urlsplit(target_url).path.casefold())
        if len(term) > 2
    }
    anchor_terms = set(re.split(r"[^a-z0-9]+", value))
    overlap = path_terms & anchor_terms
    if path_terms and overlap == path_terms:
        return AnchorClassification.EXACT_MATCH, Decimal("0.75")
    if overlap:
        return AnchorClassification.PARTIAL_MATCH, Decimal("0.70")
    return AnchorClassification.OTHER, Decimal("0.60")


def follow_state(rel: tuple[str, ...]) -> AuthorityFollowState:
    return AuthorityFollowState.NOFOLLOW if "nofollow" in rel else AuthorityFollowState.FOLLOWED


def link_type(value: str) -> AuthorityLinkType:
    try:
        return AuthorityLinkType(value.upper())
    except ValueError:
        return AuthorityLinkType.OTHER


def hhi(counts: list[int]) -> Decimal:
    total = sum(counts)
    if total <= 0:
        return Decimal("0")
    return sum(((Decimal(item) / Decimal(total)) ** 2 for item in counts), Decimal("0"))


def net_change(new_count: int, lost_count: int) -> int:
    return new_count - lost_count
