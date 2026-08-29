from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_EVENTS = 50


class TelemetryEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID
    event_name: str = Field(min_length=1, max_length=100)
    event_version: int = Field(default=1, ge=1)
    occurred_at: datetime
    page_url: Optional[str] = Field(default=None, max_length=2048)
    page_path: Optional[str] = Field(default=None, max_length=2048)
    sequence_number: Optional[int] = Field(default=None, ge=0)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class TelemetryBatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_key: str = Field(min_length=1, max_length=100)
    site_key: str = Field(min_length=1, max_length=100)
    session_key: uuid.UUID
    anonymous_visitor_key: Optional[uuid.UUID] = None
    landing_url: Optional[str] = Field(default=None, max_length=2048)
    referrer_url: Optional[str] = Field(default=None, max_length=2048)
    utm_source: Optional[str] = Field(default=None, max_length=255)
    utm_medium: Optional[str] = Field(default=None, max_length=255)
    utm_campaign: Optional[str] = Field(default=None, max_length=255)
    utm_term: Optional[str] = Field(default=None, max_length=255)
    utm_content: Optional[str] = Field(default=None, max_length=255)
    gclid: Optional[str] = Field(default=None, max_length=512)
    msclkid: Optional[str] = Field(default=None, max_length=512)
    device_category: Optional[str] = Field(default=None, max_length=64)
    browser_family: Optional[str] = Field(default=None, max_length=128)
    os_family: Optional[str] = Field(default=None, max_length=128)
    country_code: Optional[str] = Field(default=None, pattern=r"^[A-Z]{2}$")
    region_code: Optional[str] = Field(default=None, max_length=16)
    events: list[TelemetryEventInput] = Field(min_length=1, max_length=MAX_EVENTS)


class EventError(BaseModel):
    event_id: uuid.UUID
    code: str


class TelemetryResponse(BaseModel):
    request_id: uuid.UUID
    accepted: int
    duplicates: int
    rejected: int
    errors: list[EventError]
