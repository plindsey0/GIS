from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_telemetry import setup_connection

from gis.models import (
    CalculatorRun,
    Conversion,
    IngestionRun,
    IngestionStatus,
    ProductEvent,
    ProductSession,
    Site,
    TelemetryTransportBatch,
)
from gis.telemetry.worker import TelemetryWorker


class FakeQueue:
    def __init__(
        self, messages: list[dict[str, Any]] | None = None, *, fail_delete: bool = False
    ) -> None:
        self.messages = messages or []
        self.deleted: list[str] = []
        self.fail_delete = fail_delete

    def receive_message(self, **_kwargs: object) -> dict[str, Any]:
        return {"Messages": self.messages}

    def delete_message(self, **kwargs: object) -> None:
        if self.fail_delete:
            raise RuntimeError("simulated SQS delete failure")
        self.deleted.append(str(kwargs["ReceiptHandle"]))


def message(
    site: Site,
    event_id: uuid.UUID | None = None,
    *,
    batch_id: uuid.UUID | None = None,
    session_key: uuid.UUID | None = None,
) -> dict[str, Any]:
    body = {
        "message_version": "1",
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "trace_id": str(uuid.uuid4()),
        "payload_bytes": 500,
        "batch": {
            "schema_version": "1",
            "site_public_id": str(site.public_id),
            "batch_id": str(batch_id or uuid.uuid4()),
            "session_key": str(session_key or uuid.uuid4()),
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
    run = session.get(IngestionRun, batch.ingestion_run_id)
    assert run and run.status is IngestionStatus.SUCCEEDED and run.completed_at is not None
    assert event.ingestion_run_id == run.id
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


def test_logical_batch_duplicate_with_new_message_id_is_deleted_once(session: Session) -> None:
    setup_connection(session)
    site = session.scalar(select(Site))
    assert site
    logical_batch = uuid.uuid4()
    event_id = uuid.uuid4()
    first = message(site, event_id, batch_id=logical_batch)
    second = message(site, event_id, batch_id=logical_batch)
    assert first["MessageId"] != second["MessageId"]
    queue = FakeQueue([first, second])
    counters = TelemetryWorker(session, queue, "queue").poll_once(wait_seconds=0)
    assert counters["processed"] == 2 and counters["duplicates"] == 1
    assert session.scalar(select(func.count()).select_from(ProductEvent)) == 1
    assert session.scalar(select(func.count()).select_from(TelemetryTransportBatch)) == 1
    assert session.scalar(select(func.count()).select_from(IngestionRun)) == 1
    assert queue.deleted == [first["ReceiptHandle"], second["ReceiptHandle"]]


def test_same_sqs_message_retry_is_safe(session: Session) -> None:
    setup_connection(session)
    site = session.scalar(select(Site))
    assert site
    first = message(site)
    retry = {**first, "ReceiptHandle": str(uuid.uuid4())}
    queue = FakeQueue([first, retry])
    counters = TelemetryWorker(session, queue, "queue").poll_once(wait_seconds=0)
    assert counters["processed"] == 2 and counters["duplicates"] == 1
    assert session.scalar(select(func.count()).select_from(ProductEvent)) == 1
    assert session.scalar(select(func.count()).select_from(TelemetryTransportBatch)) == 1
    assert session.scalar(select(func.count()).select_from(IngestionRun)) == 1
    assert queue.deleted == [first["ReceiptHandle"], retry["ReceiptHandle"]]


def test_failure_before_commit_rolls_back_all_staged_state(session: Session) -> None:
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
            "event_name": "calculator_start",
            "event_version": 1,
            "occurred_at": now,
            "properties": {
                "calculator_run_key": run_key,
                "calculator_type": "generic",
                "input_schema_version": "1",
            },
        },
        {
            "event_id": str(uuid.uuid4()),
            "event_name": "lead_form_complete",
            "event_version": 1,
            "occurred_at": now,
            "properties": {"form_id": "lead", "calculator_run_key": run_key},
        },
    ]
    queued["Body"] = json.dumps(body)
    queue = FakeQueue([queued])

    def fail_before_commit() -> None:
        raise RuntimeError("injected pre-commit failure")

    counters = TelemetryWorker(session, queue, "queue", before_commit=fail_before_commit).poll_once(
        wait_seconds=0
    )
    assert counters["failed"] == 1 and queue.deleted == []
    for model in (
        ProductEvent,
        ProductSession,
        CalculatorRun,
        Conversion,
        TelemetryTransportBatch,
        IngestionRun,
    ):
        assert session.scalar(select(func.count()).select_from(model)) == 0


def test_commit_before_delete_failure_retries_without_duplicates(session: Session) -> None:
    setup_connection(session)
    site = session.scalar(select(Site))
    assert site
    logical_batch = uuid.uuid4()
    first = message(site, batch_id=logical_batch)
    first_queue = FakeQueue([first], fail_delete=True)
    first_counters = TelemetryWorker(session, first_queue, "queue").poll_once(wait_seconds=0)
    assert first_counters["failed"] == 1 and first_queue.deleted == []

    retry = message(site, batch_id=logical_batch)
    retry_queue = FakeQueue([retry])
    retry_counters = TelemetryWorker(session, retry_queue, "queue").poll_once(wait_seconds=0)
    assert retry_counters["processed"] == 1 and retry_queue.deleted == [retry["ReceiptHandle"]]
    assert session.scalar(select(func.count()).select_from(ProductEvent)) == 1
    assert session.scalar(select(func.count()).select_from(TelemetryTransportBatch)) == 1
    assert session.scalar(select(func.count()).select_from(IngestionRun)) == 1


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
    assert session.scalar(select(func.count()).select_from(ProductEvent)) == 0
    assert session.scalar(select(func.count()).select_from(ProductSession)) == 0
    assert session.scalar(select(func.count()).select_from(TelemetryTransportBatch)) == 0
    assert session.scalar(select(func.count()).select_from(IngestionRun)) == 0


def test_partial_canonical_rejection_rolls_back_valid_event(session: Session) -> None:
    setup_connection(session)
    site = session.scalar(select(Site))
    assert site
    queued = message(site)
    body = json.loads(queued["Body"])
    invalid = dict(body["batch"]["events"][0])
    invalid["event_id"] = str(uuid.uuid4())
    invalid["event_name"] = "unsupported"
    body["batch"]["events"].append(invalid)
    queued["Body"] = json.dumps(body)
    queue = FakeQueue([queued])
    counters = TelemetryWorker(session, queue, "queue").poll_once(wait_seconds=0)
    assert counters["failed"] == 1 and queue.deleted == []
    assert session.scalar(select(func.count()).select_from(ProductEvent)) == 0
    assert session.scalar(select(func.count()).select_from(ProductSession)) == 0
    assert session.scalar(select(func.count()).select_from(TelemetryTransportBatch)) == 0
    assert session.scalar(select(func.count()).select_from(IngestionRun)) == 0


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
