"""Privacy-first public telemetry validator for AWS Lambda."""

from __future__ import annotations

import base64
import json
import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import boto3

MAX_BYTES = 65_536
MAX_EVENTS = 50
EVENT_NAMES = {
    "page_view",
    "calculator_view",
    "calculator_start",
    "calculator_recalculate",
    "calculator_complete",
    "cta_view",
    "cta_click",
    "lead_form_view",
    "lead_form_start",
    "lead_form_complete",
    "outbound_click",
    "conversion",
}
PROHIBITED = re.compile(
    r"(^|_)(email|phone|name|address|password|token|cookie|income|debt|loan_amount|property_value|credit_score|financial|form_value|message)($|_)",
    re.I,
)
ALLOWED_PROPERTIES = {
    "page_view": {"page_title"},
    "calculator_view": {"calculator_type"},
    "calculator_start": {"calculator_run_key", "calculator_type", "input_schema_version"},
    "calculator_recalculate": {"calculator_run_key", "calculator_type", "input_schema_version"},
    "calculator_complete": {"calculator_run_key", "calculator_type", "result_schema_version"},
    "cta_view": {"cta_id", "cta_location", "cta_destination_type"},
    "cta_click": {"cta_id", "cta_location", "cta_destination_type"},
    "lead_form_view": {"form_id"},
    "lead_form_start": {"form_id"},
    "lead_form_complete": {"form_id", "calculator_run_key"},
    "outbound_click": {"destination_domain", "link_id"},
    "conversion": {"conversion_type", "conversion_id", "calculator_run_key"},
}


def response(status: int, code: str, origin: str | None = None) -> dict[str, object]:
    headers = {"content-type": "application/json", "cache-control": "no-store"}
    if origin:
        headers["access-control-allow-origin"] = origin
    return {"statusCode": status, "headers": headers, "body": json.dumps({"code": code})}


def safe_url(value: object, *, origin_only: bool = False) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("INVALID_URL")
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise ValueError("INVALID_URL")
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            "/" if origin_only else parts.path or "/",
            "",
            "",
        )
    )


def validate(
    payload: object, registry: dict[str, list[str]], origin: str | None
) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) - {
        "schema_version",
        "site_public_id",
        "batch_id",
        "session_key",
        "anonymous_visitor_key",
        "landing_url",
        "referrer_url",
        "device_category",
        "events",
    }:
        raise ValueError("INVALID_ENVELOPE")
    if payload.get("schema_version") != "1":
        raise ValueError("UNSUPPORTED_SCHEMA")
    for key in ("site_public_id", "batch_id", "session_key"):
        uuid.UUID(str(payload.get(key)))
    if payload.get("anonymous_visitor_key"):
        uuid.UUID(str(payload["anonymous_visitor_key"]))
    site_id = str(payload["site_public_id"])
    allowed_origins = registry.get(site_id)
    if not allowed_origins:
        raise ValueError("UNKNOWN_SITE")
    if not origin or origin not in allowed_origins:
        raise ValueError("ORIGIN_REJECTED")
    events = payload.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise ValueError("INVALID_EVENT_COUNT")
    payload["landing_url"] = safe_url(payload.get("landing_url"))
    payload["referrer_url"] = safe_url(payload.get("referrer_url"), origin_only=True)
    now = datetime.now(timezone.utc)
    for event in events:
        if not isinstance(event, dict) or set(event) - {
            "event_id",
            "event_name",
            "event_version",
            "occurred_at",
            "page_url",
            "page_path",
            "sequence_number",
            "properties",
        }:
            raise ValueError("INVALID_EVENT")
        uuid.UUID(str(event.get("event_id")))
        name = event.get("event_name")
        if name not in EVENT_NAMES or event.get("event_version") != 1:
            raise ValueError("INVALID_EVENT")
        occurred = datetime.fromisoformat(str(event.get("occurred_at")).replace("Z", "+00:00"))
        if occurred.tzinfo is None or abs((occurred - now).total_seconds()) > 730 * 86400:
            raise ValueError("INVALID_TIMESTAMP")
        props = event.get("properties", {})
        if (
            not isinstance(props, dict)
            or any(PROHIBITED.search(str(key)) for key in props)
            or set(props) - ALLOWED_PROPERTIES[str(name)]
        ):
            raise ValueError("PROHIBITED_PROPERTY")
        if len(json.dumps(props).encode()) > 4096:
            raise ValueError("INVALID_PROPERTIES")
        event["page_url"] = safe_url(event.get("page_url"))
        if event.get("page_path") is not None:
            path = urlsplit(str(event["page_path"])).path
            if not path.startswith("/") or len(path) > 2048:
                raise ValueError("INVALID_URL")
            event["page_path"] = path
    return payload


def handler(event: dict[str, object], _context: object) -> dict[str, object]:
    headers = {str(key).lower(): str(value) for key, value in (event.get("headers") or {}).items()}  # type: ignore[union-attr]
    origin = headers.get("origin")
    raw = str(event.get("body") or "")
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw, validate=True).decode()
    if len(raw.encode()) > MAX_BYTES:
        return response(413, "PAYLOAD_TOO_LARGE", origin)
    try:
        payload = validate(json.loads(raw), json.loads(os.environ["SITE_REGISTRY_JSON"]), origin)
        envelope = {
            "message_version": "1",
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "trace_id": str(uuid.uuid4()),
            "payload_bytes": len(raw.encode()),
            "batch": payload,
        }
        boto3.client("sqs").send_message(
            QueueUrl=os.environ["QUEUE_URL"],
            MessageBody=json.dumps(envelope, separators=(",", ":")),
        )
        print(
            json.dumps(
                {
                    "metric": "accepted_batch",
                    "events": len(payload["events"]),
                    "site_public_id": payload["site_public_id"],
                }
            )
        )  # type: ignore[arg-type]
        return response(202, "ACCEPTED", origin)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeError) as error:
        print(json.dumps({"metric": "rejected_batch", "reason": str(error)[:64]}))
        return response(400, "INVALID_REQUEST", origin)
    except Exception as error:
        print(json.dumps({"metric": "enqueue_failure", "error_type": type(error).__name__}))
        return response(503, "UNAVAILABLE", origin)
