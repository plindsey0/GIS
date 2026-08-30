from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from gis.models import AuthorityLinkState, AuthorityTargetType, EventSemanticClass

MAX_TARGETS = 25
MAX_ROWS = 10_000
MAX_PAGES = 100


@dataclass(frozen=True)
class AuthorityRequest:
    target_type: AuthorityTargetType
    target: str
    row_limit: int = 1000
    page_limit: int = 10
    start_at: datetime | None = None
    end_at: datetime | None = None
    retain_raw_anchor: bool = False

    def validate(self) -> None:
        if not 1 <= self.row_limit <= MAX_ROWS:
            raise ValueError(f"row_limit must be between 1 and {MAX_ROWS}")
        if not 1 <= self.page_limit <= MAX_PAGES:
            raise ValueError(f"page_limit must be between 1 and {MAX_PAGES}")
        if self.start_at and self.end_at and self.start_at > self.end_at:
            raise ValueError("start_at must not follow end_at")


@dataclass(frozen=True)
class AuthorityMetric:
    key: str
    name: str
    value: Decimal
    semantic_class: EventSemanticClass
    provider: str
    scale_min: Decimal | None = None
    scale_max: Decimal | None = None
    unit: str | None = None
    methodology_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BacklinkRecord:
    source_url: str
    target_url: str
    state: AuthorityLinkState
    provider_record_id: str | None = None
    anchor_text: str | None = None
    rel: tuple[str, ...] = ()
    link_type: str = "UNKNOWN"
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    semantic_class: EventSemanticClass = EventSemanticClass.PROVIDER_REPORTED
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorityCollection:
    provider: str
    observed_at: datetime
    task_id: str | None
    metrics: tuple[AuthorityMetric, ...]
    backlinks: tuple[BacklinkRecord, ...]
    completeness: str = "UNKNOWN"
    observation_scope: str = "BOUNDED_PROVIDER_RESULT"
    request_count: int = 1
    cost: Decimal | None = None
    currency: str = "USD"
    metadata: dict[str, Any] = field(default_factory=dict)


class AuthorityProvider(Protocol):
    def collect(self, request: AuthorityRequest) -> AuthorityCollection: ...


class JSONFixtureAuthorityProvider:
    """Explicit import adapter used for fixtures and customer-provided JSON exports."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def collect(self, request: AuthorityRequest) -> AuthorityCollection:
        request.validate()
        payload = json.loads(self.path.read_text())
        return normalize_provider_payload(payload, request)


def _time(value: object) -> datetime | None:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None


def normalize_provider_payload(
    payload: dict[str, Any], request: AuthorityRequest
) -> AuthorityCollection:
    """Normalize a documented interchange payload without coupling storage to a vendor."""
    request.validate()
    provider = str(payload.get("provider") or "import").strip().casefold()
    metrics = tuple(
        AuthorityMetric(
            key=str(item["key"]),
            name=str(item.get("name") or item["key"]),
            value=Decimal(str(item["value"])),
            semantic_class=EventSemanticClass(
                str(item.get("semantic_class") or "PROVIDER_REPORTED")
            ),
            provider=str(item.get("provider") or provider).casefold(),
            scale_min=Decimal(str(item["scale_min"]))
            if item.get("scale_min") is not None
            else None,
            scale_max=Decimal(str(item["scale_max"]))
            if item.get("scale_max") is not None
            else None,
            unit=item.get("unit"),
            methodology_version=item.get("methodology_version"),
            metadata=item.get("metadata") or {},
        )
        for item in payload.get("metrics", [])
    )
    raw_links = payload.get("backlinks", [])
    if len(raw_links) > request.row_limit:
        raw_links = raw_links[: request.row_limit]
    backlinks = tuple(
        BacklinkRecord(
            source_url=str(item["source_url"]),
            target_url=str(item["target_url"]),
            state=AuthorityLinkState(str(item.get("state") or "UNKNOWN")),
            provider_record_id=str(item["provider_record_id"])
            if item.get("provider_record_id")
            else None,
            anchor_text=item.get("anchor_text"),
            rel=tuple(str(value).casefold() for value in item.get("rel", [])),
            link_type=str(item.get("link_type") or "UNKNOWN").upper(),
            first_seen_at=_time(item.get("first_seen_at")),
            last_seen_at=_time(item.get("last_seen_at")),
            semantic_class=EventSemanticClass(
                str(item.get("semantic_class") or "PROVIDER_REPORTED")
            ),
            metadata=item.get("metadata") or {},
        )
        for item in raw_links
    )
    return AuthorityCollection(
        provider=provider,
        observed_at=_time(payload.get("observed_at")) or datetime.now().astimezone(),
        task_id=str(payload["task_id"]) if payload.get("task_id") else None,
        metrics=metrics,
        backlinks=backlinks,
        completeness=str(payload.get("completeness") or "UNKNOWN").upper(),
        observation_scope=str(payload.get("observation_scope") or "BOUNDED_PROVIDER_RESULT"),
        request_count=int(payload.get("request_count") or 1),
        cost=Decimal(str(payload["cost"])) if payload.get("cost") is not None else None,
        currency=str(payload.get("currency") or "USD").upper(),
        metadata=payload.get("metadata") or {},
    )
