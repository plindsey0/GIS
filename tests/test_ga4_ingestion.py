from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.integrations.ga4.cli import configure_connection
from gis.integrations.ga4.client import GA4Client
from gis.integrations.ga4.config import ALL_DATASETS, GA4Dataset
from gis.integrations.ga4.reports import REPORTS
from gis.integrations.ga4.service import GA4Collector, normalize_row, recent_window
from gis.models import (
    ConnectionStatus,
    GA4AcquisitionObservation,
    GA4EventObservation,
    GA4LandingPageObservation,
    IngestionStatus,
)
from gis.seed import seed


def provider_row(dataset: GA4Dataset, metric: str = "1.25") -> dict[str, Any]:
    report = REPORTS[dataset]
    dimensions = {
        "date": "20260820",
        "landingPage": "/va-loan-calculator/",
        "pagePath": "/va-loan-calculator/",
        "sessionDefaultChannelGroup": "Organic Search",
        "sessionSource": "google",
        "sessionMedium": "organic",
        "sessionCampaignName": "(not set)",
        "deviceCategory": "mobile",
        "country": "United States",
        "eventName": "calculator_submit",
    }
    return {
        "dimensionValues": [{"value": dimensions[name]} for name in report.dimensions],
        "metricValues": [
            {"value": "0.5" if name == "engagementRate" else metric} for name in report.metrics
        ],
    }


class ReportTransport:
    def __init__(self, *, fail_dataset: GA4Dataset | None = None, metric: str = "1.25") -> None:
        self.fail_dataset = fail_dataset
        self.metric = metric
        self.calls: list[tuple[str, int]] = []

    def run_report(self, property_resource: str, body: dict[str, Any]) -> dict[str, Any]:
        dimensions = tuple(item["name"] for item in body["dimensions"])
        dataset = next(item for item, report in REPORTS.items() if report.dimensions == dimensions)
        self.calls.append((dataset.value, int(body["offset"])))
        if dataset is self.fail_dataset:
            raise RuntimeError("provider unavailable")
        if int(body["offset"]):
            return {"rows": [], "rowCount": 1}
        return {"rows": [provider_row(dataset, self.metric)], "rowCount": 1}

    def get_property(self, property_resource: str) -> dict[str, Any]:
        return {"timeZone": "America/New_York"}


def setup_connection(session: Session) -> Any:
    seed(session, hostname="vahomemath.test")
    connection = configure_connection(
        session,
        tenant_slug="vahomemath",
        site_slug="vahomemath",
        property_id="123456789",
        credential_reference="env:GA4_TEST_CREDENTIALS",
        auth_mode="service_account",
    )
    connection.status = ConnectionStatus.ACTIVE
    session.commit()
    return connection


def test_normalization_preserves_dimensions_decimals_and_stable_identity(session: Session) -> None:
    connection = setup_connection(session)
    assert connection.site_id is not None
    first = normalize_row(
        provider_row(GA4Dataset.LANDING_PAGE),
        REPORTS[GA4Dataset.LANDING_PAGE],
        tenant_id=connection.tenant_id,
        site_id=connection.site_id,
        connection_id=connection.id,
        requested_date=date(2026, 8, 20),
    )
    changed = normalize_row(
        provider_row(GA4Dataset.LANDING_PAGE, "99"),
        REPORTS[GA4Dataset.LANDING_PAGE],
        tenant_id=connection.tenant_id,
        site_id=connection.site_id,
        connection_id=connection.id,
        requested_date=date(2026, 8, 20),
    )
    assert first.dimensions["landingPage"] == "/va-loan-calculator/"
    assert first.metrics["sessions"] == Decimal("1.25")
    assert first.observation_key == changed.observation_key


def test_all_fixed_reports_ingest_and_retain_rights_provenance(session: Session) -> None:
    connection = setup_connection(session)
    run = GA4Collector(session, GA4Client(ReportTransport())).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20), datasets=ALL_DATASETS
    )
    assert run.status is IngestionStatus.SUCCEEDED
    assert (run.records_received, run.records_inserted, run.records_rejected) == (3, 3, 0)
    assert run.rights_policy_id is not None
    assert run.acquisition_method.value == "AUTHENTICATED_API"
    assert run.collector_name == "gis.integrations.ga4"
    assert run.requested_start_at is not None and run.requested_end_at is not None
    for model in (
        GA4LandingPageObservation,
        GA4AcquisitionObservation,
        GA4EventObservation,
    ):
        observation: Any = session.scalar(select(model))
        assert observation is not None
        assert observation.rights_policy_id is not None
        assert observation.ingestion_run_id == run.id
    event_observation = session.scalar(select(GA4EventObservation))
    assert event_observation is not None
    assert event_observation.event_count_per_user == Decimal("1.25")


def test_event_normalization_maps_count_per_user() -> None:
    report = REPORTS[GA4Dataset.EVENTS]
    normalized = normalize_row(
        provider_row(GA4Dataset.EVENTS, "2.75"),
        report,
        tenant_id=uuid4(),
        site_id=uuid4(),
        connection_id=uuid4(),
        requested_date=date(2026, 8, 20),
    )
    assert normalized.metrics["eventCountPerUser"] == Decimal("2.75")


def test_identical_rerun_is_idempotent_and_changed_metrics_create_revision(
    session: Session,
) -> None:
    connection = setup_connection(session)
    day = date(2026, 8, 20)
    first = GA4Collector(session, GA4Client(ReportTransport())).sync(
        connection.id, day, day, datasets=(GA4Dataset.LANDING_PAGE,)
    )
    second = GA4Collector(session, GA4Client(ReportTransport())).sync(
        connection.id, day, day, datasets=(GA4Dataset.LANDING_PAGE,)
    )
    third = GA4Collector(session, GA4Client(ReportTransport(metric="2.5"))).sync(
        connection.id, day, day, datasets=(GA4Dataset.LANDING_PAGE,)
    )
    rows = session.scalars(
        select(GA4LandingPageObservation).order_by(GA4LandingPageObservation.created_at)
    ).all()
    assert (first.records_inserted, second.records_inserted, third.records_inserted) == (1, 0, 1)
    assert len(rows) == 2
    assert sum(row.effective_end is None for row in rows) == 1


def test_later_dataset_failure_commits_prior_chunk_and_marks_partial(session: Session) -> None:
    connection = setup_connection(session)
    run = GA4Collector(
        session, GA4Client(ReportTransport(fail_dataset=GA4Dataset.ACQUISITION))
    ).sync(connection.id, date(2026, 8, 20), date(2026, 8, 20), datasets=ALL_DATASETS)
    assert run.status is IngestionStatus.PARTIAL
    assert run.records_inserted == 1
    assert session.scalar(select(func.count()).select_from(GA4LandingPageObservation)) == 1
    assert session.scalar(select(func.count()).select_from(GA4AcquisitionObservation)) == 0


def test_first_dataset_failure_marks_run_failed(session: Session) -> None:
    connection = setup_connection(session)
    run = GA4Collector(
        session, GA4Client(ReportTransport(fail_dataset=GA4Dataset.LANDING_PAGE))
    ).sync(
        connection.id,
        date(2026, 8, 20),
        date(2026, 8, 20),
        datasets=(GA4Dataset.LANDING_PAGE,),
    )
    assert run.status is IngestionStatus.FAILED
    assert (run.records_received, run.records_inserted, run.error_count) == (0, 0, 1)


def test_recent_window_uses_property_timezone() -> None:
    from zoneinfo import ZoneInfo

    start, end = recent_window(
        2, ZoneInfo("America/Los_Angeles"), datetime(2026, 8, 21, 2, tzinfo=timezone.utc)
    )
    assert (start, end) == (date(2026, 8, 18), date(2026, 8, 19))
