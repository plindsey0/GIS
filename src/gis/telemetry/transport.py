from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gis.telemetry.schemas import TelemetryBatchInput

TRANSPORT_SCHEMA_VERSION = "1"
MAX_TRANSPORT_BYTES = 64 * 1024


class PublicTelemetryBatch(BaseModel):
    """Provider-neutral browser/queue contract; ownership is resolved server-side."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    site_public_id: uuid.UUID
    batch_id: uuid.UUID
    session_key: uuid.UUID
    anonymous_visitor_key: Optional[uuid.UUID] = None
    landing_url: Optional[str] = Field(default=None, max_length=2048)
    referrer_url: Optional[str] = Field(default=None, max_length=2048)
    device_category: Optional[str] = Field(default=None, max_length=64)
    events: list[dict[str, object]] = Field(min_length=1, max_length=50)

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: str) -> str:
        if value != TRANSPORT_SCHEMA_VERSION:
            raise ValueError("unsupported transport schema")
        return value

    def canonical(self, tenant_key: str, site_key: str) -> TelemetryBatchInput:
        return TelemetryBatchInput.model_validate(
            {
                "tenant_key": tenant_key,
                "site_key": site_key,
                "session_key": self.session_key,
                "anonymous_visitor_key": self.anonymous_visitor_key,
                "landing_url": self.landing_url,
                "referrer_url": self.referrer_url,
                "device_category": self.device_category,
                "events": self.events,
            }
        )


class QueueEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_version: str
    enqueued_at: datetime
    trace_id: uuid.UUID
    payload_bytes: int = Field(ge=0, le=MAX_TRANSPORT_BYTES)
    batch: PublicTelemetryBatch

    @field_validator("message_version")
    @classmethod
    def supported_message(cls, value: str) -> str:
        if value != "1":
            raise ValueError("unsupported message version")
        return value
