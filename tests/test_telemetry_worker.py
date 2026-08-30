from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_telemetry import setup_connection

from gis.models import CalculatorRun, ProductEvent, ProductSession, Site, TelemetryTransportBatch
from gis.telemetry.worker import TelemetryWorker


class FakeQueue:
    def __init__(self, messages: list[dict[str, Any]] | None = None) -> None:
        self.messages = messages or []
        self.deleted: list[str] = []

    def receive_message(self, **_kwargs: object) -> dict[str, Any]:
        return {"Messages": self.messages}

    def delete_message(self, **kwargs: object) -> None:
        self.deleted.append(str(kwargs["ReceiptHandle"]))


def message(site: Site, event_id: uuid.UUID | None = None) -> dict[str, Any]:
    body = {
        "message_version": "1",
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "trace_id": str(uuid.uuid4()),
        "payload_bytes": 500,
        "batch": {
            "schema_version": "1",
            "site_public_id": str(site.public_id),
            "batch_id": str(uuid.uuid4()),
            "session_key": str(uuid.uuid4()),
            "events": [
                {
                    "event_id": str(event_id or uuid.uuid4()),
                    "event_name": "page_view",
                    "event_version": 1,
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "page_path": "/",
                    "properties": {},
                }
            ],
        },
    }
    return {
        "MessageId": str(uuid.uuid4()),
        "ReceiptHandle": str(uuid.uuid4()),
        "Body": json.dumps(body),
    }


def test_empty_queue(session: Session) -> None:
    assert TelemetryWorker(session, FakeQueue(), "queue").poll_once(wait_seconds=0)["received"] == 0


def test_worker_persists_deletes_and_records_provenance(session: Session) -> None:
    setup_connection(session)
    site = session.scalar(select(Site))
    assert site
    queued = message(site)
    queue = FakeQueue([queued])
    counters = TelemetryWorker(session, queue, "queue").poll_once(wait_seconds=0)
    assert counters == {"received": 1, "processed": 1, "failed": 0, "events": 1, "duplicates": 0}
    event = session.scalar(select(ProductEvent))
    batch = session.scalar(select(TelemetryTransportBatch))
    assert event and event.ingestion_run_id and batch and batch.events_accepted == 1
    assert queue.deleted == [queued["ReceiptHandle"]]


def test_duplicate_delivery_and_malformed_message_are_safe(session: Session) -> None:
    setup_connection(session)
    site = session.scalar(select(Site))
    assert site
    event_id = uuid.uuid4()
    first = message(site, event_id)
    second = message(site, event_id)
    queue = FakeQueue([first, second])
    counters = TelemetryWorker(session, queue, "queue").poll_once(wait_seconds=0)
    assert counters["processed"] == 2 and counters["duplicates"] == 1
    assert session.scalar(select(func.count()).select_from(ProductEvent)) == 1
    bad = {"MessageId": "bad", "ReceiptHandle": "bad-handle", "Body": "{}"}
    bad_queue = FakeQueue([bad])
    assert TelemetryWorker(session, bad_queue, "queue").poll_once(wait_seconds=0)["failed"] == 1
    assert bad_queue.deleted == []


def test_unknown_public_site_cannot_cross_tenant(session: Session) -> None:
    setup_connection(session)
    site = session.scalar(select(Site))
    assert site
    queued = message(site)
    body = json.loads(queued["Body"])
    body["batch"]["site_public_id"] = str(uuid.uuid4())
    queued["Body"] = json.dumps(body)
    queue = FakeQueue([queued])
    assert TelemetryWorker(session, queue, "queue").poll_once(wait_seconds=0)["failed"] == 1
    assert queue.deleted == []


def test_canonical_validation_failure_is_not_deleted(session: Session) -> None:
    setup_connection(session)
    site = session.scalar(select(Site))
    assert site
    queued = message(site)
    body = json.loads(queued["Body"])
    body["batch"]["events"][0]["event_name"] = "unsupported"
    queued["Body"] = json.dumps(body)
    queue = FakeQueue([queued])
    assert TelemetryWorker(session, queue, "queue").poll_once(wait_seconds=0)["failed"] == 1
    assert queue.deleted == []


def test_fixture_end_to_end_calculator_lifecycle(session: Session) -> None:
    setup_connection(session)
    site = session.scalar(select(Site))
    assert site
    queued = message(site)
    body = json.loads(queued["Body"])
    run_key = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    body["batch"]["events"] = [
        {
            "event_id": str(uuid.uuid4()),
            "event_name": "page_view",
            "event_version": 1,
            "occurred_at": now,
            "page_path": "/calculator",
            "sequence_number": 0,
            "properties": {},
        },
        {
            "event_id": str(uuid.uuid4()),
            "event_name": "calculator_view",
            "event_version": 1,
            "occurred_at": now,
            "page_path": "/calculator",
            "sequence_number": 1,
            "properties": {"calculator_type": "generic"},
        },
        {
            "event_id": str(uuid.uuid4()),
            "event_name": "calculator_start",
            "event_version": 1,
            "occurred_at": now,
            "page_path": "/calculator",
            "sequence_number": 2,
            "properties": {
                "calculator_run_key": run_key,
                "calculator_type": "generic",
                "input_schema_version": "1",
            },
        },
        {
            "event_id": str(uuid.uuid4()),
            "event_name": "calculator_complete",
            "event_version": 1,
            "occurred_at": now,
            "page_path": "/calculator",
            "sequence_number": 3,
            "properties": {
                "calculator_run_key": run_key,
                "calculator_type": "generic",
                "result_schema_version": "1",
            },
        },
    ]
    queued["Body"] = json.dumps(body)
    queue = FakeQueue([queued])
    counters = TelemetryWorker(session, queue, "queue").poll_once(wait_seconds=0)
    assert counters["events"] == 4
    assert session.scalar(select(func.count()).select_from(ProductSession)) == 1
    assert session.scalar(select(func.count()).select_from(CalculatorRun)) == 1
    assert session.scalar(select(func.count()).select_from(ProductEvent)) == 4
