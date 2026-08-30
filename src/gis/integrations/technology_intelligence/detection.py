from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from gis.integrations.content_intelligence.retrieval import RetrievalResult
from gis.integrations.technology_intelligence.signatures import SIGNATURES, TechnologySignature


@dataclass(frozen=True)
class DetectedEvidence:
    signature_key: str
    evidence_type: str
    match_target: str
    evidence_value: str
    evidence_hash: str
    semantic_class: str
    confidence: Decimal


@dataclass(frozen=True)
class DetectedTechnology:
    technology_slug: str
    scope: str
    confidence: Decimal
    semantic_class: str
    evidence: tuple[DetectedEvidence, ...]


def _targets(result: RetrievalResult) -> dict[str, str]:
    html = result.body.decode("utf-8", errors="replace")
    generator = " ".join(
        re.findall(
            r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)',
            html,
            flags=re.IGNORECASE,
        )
    )
    headers = {key.upper().replace("-", "_"): value for key, value in result.headers.items()}
    values = {"HTML": html, "META_GENERATOR": generator}
    values.update({f"HEADER_{key}": value for key, value in headers.items()})
    cookie_header = result.headers.get("Set-Cookie", "")
    values["COOKIE"] = " ".join(re.findall(r"(?:^|,)\s*([^=;,\s]+)=", cookie_header))
    return values


def _matches(signature: TechnologySignature, value: str) -> bool:
    if signature.match_type == "PRESENT":
        return bool(value)
    if signature.match_type == "EXACT":
        return value.casefold() == signature.pattern.casefold()
    if signature.match_type == "REGEX":
        return re.search(signature.pattern, value, flags=re.IGNORECASE) is not None
    return signature.pattern.casefold() in value.casefold()


def detect_technologies(result: RetrievalResult) -> list[DetectedTechnology]:
    targets = _targets(result)
    grouped: dict[tuple[str, str], list[DetectedEvidence]] = defaultdict(list)
    for signature in SIGNATURES:
        value = targets.get(signature.target, "")
        if not signature.active or not _matches(signature, value):
            continue
        safe_value = value[:500]
        grouped[(signature.technology_slug, signature.scope)].append(
            DetectedEvidence(
                signature.key,
                signature.target.split("_", 1)[0],
                signature.target,
                safe_value,
                hashlib.sha256(safe_value.encode()).hexdigest(),
                signature.semantic_class,
                signature.confidence,
            )
        )
    detections = []
    for (slug, scope), evidence in grouped.items():
        semantics = (
            "MEASURED"
            if all(item.semantic_class == "MEASURED" for item in evidence)
            else "HEURISTIC"
        )
        detections.append(
            DetectedTechnology(
                slug, scope, max(item.confidence for item in evidence), semantics, tuple(evidence)
            )
        )
    return sorted(detections, key=lambda item: (item.technology_slug, item.scope))
