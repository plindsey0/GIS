from __future__ import annotations

import argparse
import json
import logging
import signal
import time
from datetime import datetime, timezone
from typing import Any, Protocol

import boto3
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.models import (
    IngestionRun,
    IngestionStatus,
    Site,
    TelemetryTransportBatch,
    Tenant,
)
from gis.telemetry.service import TelemetryService, resolve_context
from gis.telemetry.transport import QueueEnvelope

LOGGER = logging.getLogger(__name__)


class QueueClient(Protocol):
    def receive_message(self, **kwargs: object) -> dict[str, Any]: ...

    def delete_message(self, **kwargs: object) -> object: ...


class TelemetryWorker:
    def __init__(self, session: Session, queue: QueueClient, queue_url: str) -> None:
        self.session = session
        self.queue = queue
        self.queue_url = queue_url

    def poll_once(self, *, wait_seconds: int = 20, max_messages: int = 10) -> dict[str, int]:
        response = self.queue.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_seconds,
            AttributeNames=["ApproximateReceiveCount"],
        )
        counters = {"received": 0, "processed": 0, "failed": 0, "events": 0, "duplicates": 0}
        for message in response.get("Messages", []):
            counters["received"] += 1
            try:
                result = self.process_message(str(message["MessageId"]), str(message["Body"]))
                self.queue.delete_message(
                    QueueUrl=self.queue_url, ReceiptHandle=message["ReceiptHandle"]
                )
                counters["processed"] += 1
                counters["events"] += result["accepted"]
                counters["duplicates"] += result["duplicates"]
            except (ValidationError, LookupError, ValueError, IntegrityError, KeyError) as error:
                self.session.rollback()
                counters["failed"] += 1
                LOGGER.warning(
                    "telemetry_message_failed",
                    extra={
                        "message_id": message.get("MessageId"),
                        "error_type": type(error).__name__,
                    },
                )
        return counters

    def process_message(self, message_id: str, body: str) -> dict[str, int]:
        existing = self.session.scalar(
            select(TelemetryTransportBatch).where(
                TelemetryTransportBatch.transport == "aws_sqs",
                TelemetryTransportBatch.transport_message_id == message_id,
            )
        )
        if existing:
            return {"accepted": 0, "duplicates": existing.events_received}
        envelope = QueueEnvelope.model_validate_json(body)
        site = self.session.scalar(
            select(Site).where(Site.public_id == envelope.batch.site_public_id)
        )
        if site is None:
            raise LookupError("public telemetry site not found")
        tenant = self.session.get(Tenant, site.tenant_id)
        if tenant is None:
            raise LookupError("telemetry tenant not found")
        context = resolve_context(self.session, tenant.slug, site.slug)
        now = datetime.now(timezone.utc)
        run = IngestionRun(
            tenant_id=tenant.id,
            site_id=site.id,
            data_source_connection_id=context.connection.id,
            started_at=now,
            status=IngestionStatus.RUNNING,
            records_received=len(envelope.batch.events),
            rights_policy_id=context.rights_policy_id,
            acquisition_method=context.source.acquisition_method,
            collector_name="gis.telemetry.aws_sqs",
            collector_version="1",
            schema_version=envelope.batch.schema_version,
            source_metadata={
                "transport": "aws_sqs",
                "message_id": message_id,
                "batch_id": str(envelope.batch.batch_id),
                "trace_id": str(envelope.trace_id),
            },
        )
        self.session.add(run)
        self.session.flush()
        result = TelemetryService(self.session).ingest(
            envelope.batch.canonical(tenant.slug, site.slug),
            context,
            ingestion_run_id=run.id,
            now=now,
        )
        if result.rejected:
            run.status = IngestionStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            run.records_inserted = result.accepted
            run.records_rejected = result.rejected
            run.error_count = result.rejected
            run.error_summary = "canonical telemetry validation rejected one or more events"
            self.session.commit()
            raise ValueError("canonical telemetry validation failed")
        run.status = IngestionStatus.SUCCEEDED
        run.completed_at = datetime.now(timezone.utc)
        run.records_inserted = result.accepted
        run.records_rejected = result.rejected
        run.error_count = result.rejected
        self.session.add(
            TelemetryTransportBatch(
                tenant_id=tenant.id,
                site_id=site.id,
                ingestion_run_id=run.id,
                transport="aws_sqs",
                transport_message_id=message_id,
                batch_id=envelope.batch.batch_id,
                schema_version=envelope.batch.schema_version,
                events_received=len(envelope.batch.events),
                events_accepted=result.accepted,
                events_rejected=result.rejected,
                duplicates_ignored=result.duplicates,
                payload_bytes=envelope.payload_bytes,
                processed_at=run.completed_at,
            )
        )
        self.session.commit()
        return {"accepted": result.accepted, "duplicates": result.duplicates}


def run(queue_url: str, *, once: bool = False, profile: str | None = None) -> int:
    aws_session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    queue = aws_session.client("sqs")
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with session_factory()() as session:
        worker = TelemetryWorker(session, queue, queue_url)
        while not stopping:
            counters = worker.poll_once()
            print(json.dumps(counters, separators=(",", ":")))
            if once:
                break
            if not counters["received"]:
                time.sleep(1)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="gis-telemetry-worker")
    parser.add_argument("run", nargs="?")
    parser.add_argument("--queue-url", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(args.queue_url, once=args.once, profile=args.profile))
