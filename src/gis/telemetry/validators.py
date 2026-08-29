from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from gis.telemetry.schemas import TelemetryEventInput

MAX_PROPERTIES_BYTES = 4096
FUTURE_TOLERANCE = timedelta(hours=24)
OLDEST_EVENT = timedelta(days=730)
PROHIBITED_FIELDS = {
    "email",
    "phone",
    "phone_number",
    "name",
    "full_name",
    "address",
    "street_address",
    "ssn",
    "social_security_number",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "annual_income",
    "home_price",
    "loan_amount",
    "form_body",
    "message",
}

BASE_ALLOWED: dict[str, set[str]] = {
    "page_view": {"page_title"},
    "calculator_view": {"calculator_type"},
    "calculator_start": {
        "calculator_run_key",
        "calculator_type",
        "input_schema_version",
        "home_price_bucket",
        "down_payment_bucket",
        "loan_amount_bucket",
        "interest_rate_bucket",
        "loan_term",
        "state_code",
        "funding_fee_category",
        "funding_fee_exempt",
        "first_time_va_use",
        "property_type_category",
    },
    "calculator_recalculate": {
        "calculator_run_key",
        "calculator_type",
        "input_schema_version",
        "home_price_bucket",
        "down_payment_bucket",
        "loan_amount_bucket",
        "interest_rate_bucket",
        "loan_term",
        "state_code",
        "funding_fee_category",
        "funding_fee_exempt",
        "first_time_va_use",
        "property_type_category",
    },
    "calculator_complete": {
        "calculator_run_key",
        "calculator_type",
        "result_schema_version",
        "monthly_payment_bucket",
        "loan_amount_bucket",
        "funding_fee_category",
        "funding_fee_exempt",
    },
    "cta_view": {"cta_id", "cta_location", "cta_destination_type"},
    "cta_click": {"cta_id", "cta_location", "cta_destination_type"},
    "lead_form_view": {"form_id"},
    "lead_form_start": {"form_id"},
    "lead_form_complete": {"form_id", "calculator_run_key"},
    "outbound_click": {"destination_domain", "link_id"},
    "conversion": {
        "conversion_type",
        "conversion_id",
        "calculator_run_key",
        "conversion_value",
        "currency",
    },
}
CALCULATOR_REQUIRED = {
    "calculator_start": {"calculator_run_key", "calculator_type", "input_schema_version"},
    "calculator_recalculate": {"calculator_run_key", "calculator_type", "input_schema_version"},
    "calculator_complete": {"calculator_run_key", "calculator_type", "result_schema_version"},
}
EVENT_REQUIRED = {"conversion": {"conversion_type"}}


class EventValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def validate_event(event: TelemetryEventInput, now: datetime) -> dict[str, Any]:
    if event.event_name not in BASE_ALLOWED:
        raise EventValidationError("UNKNOWN_EVENT")
    if event.event_version != 1:
        raise EventValidationError("UNSUPPORTED_EVENT_VERSION")
    occurred = event.occurred_at.astimezone(timezone.utc)
    if occurred > now + FUTURE_TOLERANCE or occurred < now - OLDEST_EVENT:
        raise EventValidationError("INVALID_TIMESTAMP")
    properties = event.properties
    if len(json.dumps(properties, separators=(",", ":")).encode()) > MAX_PROPERTIES_BYTES:
        raise EventValidationError("PAYLOAD_TOO_LARGE")
    lowered = {key.lower() for key in properties}
    if lowered & PROHIBITED_FIELDS:
        raise EventValidationError("PROHIBITED_PROPERTY")
    allowed = BASE_ALLOWED[event.event_name]
    if set(properties) - allowed:
        raise EventValidationError("INVALID_EVENT_PROPERTIES")
    if CALCULATOR_REQUIRED.get(event.event_name, set()) - set(properties):
        raise EventValidationError("INVALID_EVENT_PROPERTIES")
    if EVENT_REQUIRED.get(event.event_name, set()) - set(properties):
        raise EventValidationError("INVALID_EVENT_PROPERTIES")
    for key in ("calculator_run_key", "conversion_id"):
        if key in properties:
            try:
                uuid.UUID(str(properties[key]))
            except ValueError as error:
                raise EventValidationError("INVALID_EVENT_PROPERTIES") from error
    return properties


def sanitize_url(value: str | None) -> str | None:
    if value is None:
        return None
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise EventValidationError("INVALID_URL")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def sanitize_path(value: str | None) -> str | None:
    if value is None:
        return None
    path = urlsplit(value).path
    if not path.startswith("/") or len(path) > 2048:
        raise EventValidationError("INVALID_URL")
    return path
