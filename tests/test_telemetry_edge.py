from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def load_edge() -> ModuleType:
    path = Path("infrastructure/telemetry/edge/app.py")
    spec = importlib.util.spec_from_file_location("telemetry_edge", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SITE_ID = "10000000-0000-4000-8000-000000000001"
ORIGIN = "https://www.example.com"


def payload(event_count: int = 1) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "site_public_id": SITE_ID,
        "batch_id": str(uuid.uuid4()),
        "session_key": str(uuid.uuid4()),
        "landing_url": f"{ORIGIN}/calculator?token=removed",
        "referrer_url": "https://google.com/search?q=removed",
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_name": "page_view",
                "event_version": 1,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "page_path": "/calculator?email=removed",
                "properties": {"page_title": "Calculator"},
            }
            for _ in range(event_count)
        ],
    }


class FakeSqs:
    def __init__(self, fail: bool = False) -> None:
        self.messages: list[dict[str, object]] = []
        self.fail = fail

    def send_message(self, **kwargs: object) -> None:
        if self.fail:
            raise RuntimeError("no queue")
        self.messages.append(kwargs)


def invoke(
    monkeypatch: pytest.MonkeyPatch,
    body: object,
    *,
    origin: str = ORIGIN,
    sqs: FakeSqs | None = None,
) -> tuple[dict[str, object], FakeSqs]:
    edge = load_edge()
    queue = sqs or FakeSqs()
    monkeypatch.setenv("SITE_REGISTRY_JSON", json.dumps({SITE_ID: [ORIGIN]}))
    monkeypatch.setenv("QUEUE_URL", "https://sqs.invalid/queue")
    monkeypatch.setattr(edge.boto3, "client", lambda _service: queue)
    event = {"headers": {"origin": origin}, "body": json.dumps(body)}
    return edge.handler(event, object()), queue


def test_valid_single_event_and_batch_are_queued(monkeypatch: pytest.MonkeyPatch) -> None:
    single, queue = invoke(monkeypatch, payload())
    assert single["statusCode"] == 202
    many, queue = invoke(monkeypatch, payload(3), sqs=queue)
    assert many["statusCode"] == 202 and len(queue.messages) == 2
    envelope = json.loads(str(queue.messages[0]["MessageBody"]))
    assert envelope["message_version"] == "1" and envelope["batch"]["site_public_id"] == SITE_ID


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(site_public_id=str(uuid.uuid4())),
        lambda value: value.update(schema_version="99"),
        lambda value: value["events"][0].update(event_name="unknown"),
        lambda value: value["events"][0].update(event_id="bad"),
        lambda value: value["events"][0].update(properties={"email": "private@example.com"}),
        lambda value: value["events"][0].update(page_url="javascript:alert(1)"),
    ],
)
def test_invalid_requests_are_rejected(monkeypatch: pytest.MonkeyPatch, mutation: Any) -> None:
    value = payload()
    mutation(value)
    response, queue = invoke(monkeypatch, value)
    assert response["statusCode"] == 400 and not queue.messages


def test_query_strings_are_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    response, queue = invoke(monkeypatch, payload())
    assert response["statusCode"] == 202
    body = json.loads(str(queue.messages[0]["MessageBody"]))["batch"]
    assert (
        body["landing_url"] == f"{ORIGIN}/calculator"
        and body["referrer_url"] == "https://google.com/"
    )
    assert body["events"][0]["page_path"] == "/calculator"


def test_origin_count_size_json_and_enqueue_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    rejected, _ = invoke(monkeypatch, payload(), origin="https://evil.example")
    assert rejected["statusCode"] == 400
    too_many, _ = invoke(monkeypatch, payload(51))
    assert too_many["statusCode"] == 400
    edge = load_edge()
    malformed = edge.handler({"headers": {"origin": ORIGIN}, "body": "{"}, object())
    assert malformed["statusCode"] == 400
    oversized = edge.handler({"headers": {"origin": ORIGIN}, "body": "x" * 65537}, object())
    assert oversized["statusCode"] == 413
    unavailable, _ = invoke(monkeypatch, payload(), sqs=FakeSqs(fail=True))
    assert unavailable["statusCode"] == 503


def test_no_secrets_or_payloads_are_logged_or_configured() -> None:
    source = Path("infrastructure/telemetry/edge/app.py").read_text()
    template = Path("infrastructure/telemetry/template.yaml").read_text()
    assert "AWS_SECRET_ACCESS_KEY" not in source + template
    assert "AdministratorAccess" not in template
