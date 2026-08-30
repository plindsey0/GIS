from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.ga4.client import GA4Client
from gis.integrations.ga4.config import GA4ConfigurationError, GA4ConnectionConfig, GA4Dataset
from gis.integrations.ga4.reports import REPORTS, ReportSpec
from gis.models import (
    ConnectionStatus,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    GA4AcquisitionObservation,
    GA4EventObservation,
    GA4LandingPageObservation,
    IngestionRun,
    IngestionStatus,
    QualityFlag,
)

LOGGER = logging.getLogger(__name__)


class GA4IngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizedGA4Row:
    observation_key: str
    observed_date: date
    dimensions: dict[str, str]
    metrics: dict[str, Decimal]


def validate_connection(
    connection: DataSourceConnection, source: DataSource
) -> GA4ConnectionConfig:
    if source.key != "ga4":
        raise GA4ConfigurationError("connection is not for ga4")
    if connection.site_id is None:
        raise GA4ConfigurationError("GA4 connections must be scoped to a site")
    if not connection.credential_reference:
        raise GA4ConfigurationError("credential_reference is required")
    return GA4ConnectionConfig.from_json(connection.configuration_json)


def date_chunks(start_date: date, end_date: date) -> list[tuple[date, date]]:
    if end_date < start_date:
        raise GA4ConfigurationError("end_date must be on or after start_date")
    return [
        (start_date + timedelta(days=offset), start_date + timedelta(days=offset))
        for offset in range((end_date - start_date).days + 1)
    ]


def recent_window(
    recent_days: int, reporting_timezone: ZoneInfo, now: datetime | None = None
) -> tuple[date, date]:
    if recent_days < 1:
        raise GA4ConfigurationError("recent_days must be positive")
    current_date = (now or datetime.now(timezone.utc)).astimezone(reporting_timezone).date()
    end_date = current_date - timedelta(days=1)
    return end_date - timedelta(days=recent_days - 1), end_date


def normalize_row(
    row: dict[str, Any],
    report: ReportSpec,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    connection_id: uuid.UUID,
    requested_date: date,
) -> NormalizedGA4Row:
    dimension_values = row.get("dimensionValues")
    metric_values = row.get("metricValues")
    if not isinstance(dimension_values, list) or len(dimension_values) != len(report.dimensions):
        raise GA4IngestionError("dimension values do not match report specification")
    if not isinstance(metric_values, list) or len(metric_values) != len(report.metrics):
        raise GA4IngestionError("metric values do not match report specification")
    dimensions = {
        name: _provider_value(value, "dimension")
        for name, value in zip(report.dimensions, dimension_values)
    }
    try:
        observed_date = datetime.strptime(dimensions["date"], "%Y%m%d").date()
    except ValueError as error:
        raise GA4IngestionError("row has invalid date") from error
    if observed_date != requested_date:
        raise GA4IngestionError("row date does not match requested chunk")
    metrics = {
        name: _metric(_provider_value(value, "metric"), name)
        for name, value in zip(report.metrics, metric_values)
    }
    if metrics.get("engagementRate", Decimal(0)) > 1:
        raise GA4IngestionError("engagementRate must not exceed 1")
    identity = [
        str(tenant_id),
        str(site_id),
        str(connection_id),
        report.dataset.value,
        observed_date.isoformat(),
        *[dimensions[name] for name in report.dimensions if name != "date"],
    ]
    observation_key = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return NormalizedGA4Row(observation_key, observed_date, dimensions, metrics)


class GA4Collector:
    def __init__(self, session: Session, client: GA4Client) -> None:
        self.session = session
        self.client = client

    def sync(
        self,
        connection_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        *,
        recent_days: int = 3,
        datasets: tuple[GA4Dataset, ...] | None = None,
        dry_run: bool = False,
    ) -> IngestionRun:
        connection, source = self._connection(connection_id)
        config = validate_connection(connection, source)
        if connection.status is not ConnectionStatus.ACTIVE:
            raise GA4ConfigurationError("connection must be ACTIVE; run validate first")
        rights_policy_id = connection.rights_policy_id or source.default_rights_policy_id
        if rights_policy_id is None or self.session.get(DataRightsPolicy, rights_policy_id) is None:
            raise GA4ConfigurationError("no applicable data-rights policy")
        if (start_date is None) != (end_date is None):
            raise GA4ConfigurationError("start_date and end_date must be supplied together")
        requested_datasets = datasets or config.default_datasets
        if not requested_datasets:
            raise GA4ConfigurationError("at least one dataset is required")
        run = self._start_run(connection, source, rights_policy_id)
        completed_chunks = 0
        try:
            timezone_name = self.client.property_timezone(config.property_resource)
            reporting_timezone = _timezone(timezone_name)
            if config.property_timezone and config.property_timezone != timezone_name:
                raise GA4ConfigurationError(
                    "configured property_timezone does not match GA4 property metadata"
                )
            if start_date is None or end_date is None:
                start_date, end_date = recent_window(recent_days, reporting_timezone)
            run.requested_start_at = datetime.combine(start_date, datetime.min.time(), timezone.utc)
            run.requested_end_at = datetime.combine(end_date, datetime.max.time(), timezone.utc)
            self.session.commit()
            for chunk_start, chunk_end in date_chunks(start_date, end_date):
                for dataset in requested_datasets:
                    report = REPORTS[dataset]
                    rows = list(
                        self.client.iter_rows(
                            config.property_resource, report, chunk_start, chunk_end
                        )
                    )
                    received, inserted, rejected = self._persist_chunk(
                        run,
                        connection,
                        report,
                        rights_policy_id,
                        reporting_timezone,
                        chunk_start,
                        rows,
                        dry_run=dry_run,
                    )
                    run.records_received += received
                    run.records_inserted += inserted
                    run.records_rejected += rejected
                    run.error_count += rejected
                    if rejected:
                        run.error_summary = f"{rejected} malformed GA4 row(s) rejected"
                    run.source_cursor = f"{dataset.value}:{chunk_end.isoformat()}"
                    connection.last_attempted_sync_at = _now()
                    self.session.commit()
                    completed_chunks += 1
                    LOGGER.info(
                        "ga4_chunk_complete",
                        extra={
                            "connection_id": str(connection.id),
                            "site_id": str(connection.site_id),
                            "run_id": str(run.id),
                            "property_id": config.property_id,
                            "date": chunk_start.isoformat(),
                            "dataset": dataset.value,
                            "rows": received,
                        },
                    )
        except Exception as error:
            self.session.rollback()
            refreshed_run = self.session.get(IngestionRun, run.id)
            if refreshed_run is None:
                raise GA4IngestionError("ingestion run disappeared") from error
            run = refreshed_run
            run.status = IngestionStatus.PARTIAL if completed_chunks else IngestionStatus.FAILED
            run.completed_at = _now()
            run.error_count += 1
            run.error_summary = f"{type(error).__name__}: {error}"
            self.session.commit()
            LOGGER.exception(
                "ga4_chunk_failed",
                extra={"connection_id": str(connection_id), "run_id": str(run.id)},
            )
            return run
        run.status = IngestionStatus.PARTIAL if run.records_rejected else IngestionStatus.SUCCEEDED
        run.completed_at = _now()
        refreshed_connection = self.session.get(DataSourceConnection, connection_id)
        if refreshed_connection is not None:
            refreshed_connection.last_attempted_sync_at = run.completed_at
            if run.status is IngestionStatus.SUCCEEDED:
                refreshed_connection.last_successful_sync_at = run.completed_at
        self.session.commit()
        return run

    def _connection(self, connection_id: uuid.UUID) -> tuple[DataSourceConnection, DataSource]:
        connection = self.session.get(DataSourceConnection, connection_id)
        if connection is None:
            raise GA4ConfigurationError("connection not found")
        source = self.session.get(DataSource, connection.data_source_id)
        if source is None:
            raise GA4ConfigurationError("connection source not found")
        return connection, source

    def _start_run(
        self, connection: DataSourceConnection, source: DataSource, rights_policy_id: uuid.UUID
    ) -> IngestionRun:
        run = IngestionRun(
            tenant_id=connection.tenant_id,
            site_id=connection.site_id,
            data_source_connection_id=connection.id,
            started_at=_now(),
            status=IngestionStatus.PENDING,
            rights_policy_id=rights_policy_id,
            acquisition_method=source.acquisition_method,
            collector_name="gis.integrations.ga4",
            collector_version="1",
            schema_version="1",
        )
        self.session.add(run)
        self.session.commit()
        run.status = IngestionStatus.RUNNING
        self.session.commit()
        return run

    def _persist_chunk(
        self,
        run: IngestionRun,
        connection: DataSourceConnection,
        report: ReportSpec,
        rights_policy_id: uuid.UUID,
        reporting_timezone: ZoneInfo,
        observed_date: date,
        rows: list[dict[str, Any]],
        *,
        dry_run: bool,
    ) -> tuple[int, int, int]:
        normalized: list[NormalizedGA4Row] = []
        rejected = 0
        assert connection.site_id is not None
        for provider_row in rows:
            try:
                normalized.append(
                    normalize_row(
                        provider_row,
                        report,
                        tenant_id=connection.tenant_id,
                        site_id=connection.site_id,
                        connection_id=connection.id,
                        requested_date=observed_date,
                    )
                )
            except GA4IngestionError:
                rejected += 1
        if dry_run or not normalized:
            return len(rows), 0, rejected
        model: Any = _model(report.dataset)
        keys = [row.observation_key for row in normalized]
        currents = self.session.scalars(
            select(model).where(model.observation_key.in_(keys), model.effective_end.is_(None))
        ).all()
        current_by_key = {row.observation_key: row for row in currents}
        revision_time = _now()
        additions = []
        for row in normalized:
            current = current_by_key.get(row.observation_key)
            if current is not None and _metrics_equal(current, row, report):
                continue
            if current is not None:
                current.effective_end = revision_time
            additions.append(
                model(
                    **_observation_values(
                        run,
                        connection,
                        report,
                        rights_policy_id,
                        reporting_timezone,
                        revision_time,
                        row,
                    )
                )
            )
        self.session.add_all(additions)
        self.session.flush()
        return len(rows), len(additions), rejected


def _observation_values(
    run: IngestionRun,
    connection: DataSourceConnection,
    report: ReportSpec,
    rights_policy_id: uuid.UUID,
    reporting_timezone: ZoneInfo,
    revision_time: datetime,
    row: NormalizedGA4Row,
) -> dict[str, Any]:
    common: dict[str, Any] = {
        "tenant_id": connection.tenant_id,
        "site_id": connection.site_id,
        "data_source_connection_id": connection.id,
        "ingestion_run_id": run.id,
        "rights_policy_id": rights_policy_id,
        "source_record_id": row.observation_key,
        "observation_key": row.observation_key,
        "observed_date": row.observed_date,
        "observed_at": datetime.combine(
            row.observed_date, time.min, tzinfo=reporting_timezone
        ).astimezone(timezone.utc),
        "effective_start": revision_time,
        "quality_flag": QualityFlag.VALID,
    }
    dimensions = row.dimensions
    metrics = row.metrics
    if report.dataset is GA4Dataset.LANDING_PAGE:
        return {
            **common,
            "landing_page": dimensions["landingPage"],
            "landing_page_hash": _text_hash(dimensions["landingPage"]),
            "session_default_channel_group": dimensions["sessionDefaultChannelGroup"],
            "session_source": dimensions["sessionSource"],
            "session_medium": dimensions["sessionMedium"],
            "device_category": dimensions["deviceCategory"],
            "country": dimensions["country"],
            "sessions": metrics["sessions"],
            "active_users": metrics["activeUsers"],
            "new_users": metrics["newUsers"],
            "engaged_sessions": metrics["engagedSessions"],
            "engagement_rate": metrics["engagementRate"],
            "average_session_duration": metrics["averageSessionDuration"],
            "event_count": metrics["eventCount"],
            "key_events": metrics["keyEvents"],
        }
    if report.dataset is GA4Dataset.ACQUISITION:
        return {
            **common,
            "session_default_channel_group": dimensions["sessionDefaultChannelGroup"],
            "session_source": dimensions["sessionSource"],
            "source_hash": _text_hash(dimensions["sessionSource"]),
            "session_medium": dimensions["sessionMedium"],
            "medium_hash": _text_hash(dimensions["sessionMedium"]),
            "session_campaign": dimensions["sessionCampaignName"],
            "device_category": dimensions["deviceCategory"],
            "country": dimensions["country"],
            "sessions": metrics["sessions"],
            "active_users": metrics["activeUsers"],
            "new_users": metrics["newUsers"],
            "engaged_sessions": metrics["engagedSessions"],
            "engagement_rate": metrics["engagementRate"],
            "event_count": metrics["eventCount"],
            "key_events": metrics["keyEvents"],
        }
    return {
        **common,
        "event_name": dimensions["eventName"],
        "event_name_hash": _text_hash(dimensions["eventName"]),
        "landing_page": dimensions["landingPage"],
        "page_path": dimensions["pagePath"],
        "session_default_channel_group": dimensions["sessionDefaultChannelGroup"],
        "device_category": dimensions["deviceCategory"],
        "country": dimensions["country"],
        "event_count": metrics["eventCount"],
        "total_users": metrics["totalUsers"],
        "event_count_per_user": metrics["eventCountPerUser"],
        "key_events": metrics["keyEvents"],
    }


def _provider_value(value: Any, kind: str) -> str:
    if not isinstance(value, dict) or not isinstance(value.get("value"), str):
        raise GA4IngestionError(f"{kind} value is malformed")
    result: str = value["value"]
    return result


def _metric(value: str, name: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise GA4IngestionError(f"{name} is not numeric") from error
    if not result.is_finite() or result < 0:
        raise GA4IngestionError(f"{name} must be finite and nonnegative")
    return result


def _model(dataset: GA4Dataset) -> Any:
    if dataset is GA4Dataset.LANDING_PAGE:
        return GA4LandingPageObservation
    if dataset is GA4Dataset.ACQUISITION:
        return GA4AcquisitionObservation
    return GA4EventObservation


def _metrics_equal(current: Any, row: NormalizedGA4Row, report: ReportSpec) -> bool:
    field_names = {
        "sessions": "sessions",
        "activeUsers": "active_users",
        "newUsers": "new_users",
        "engagedSessions": "engaged_sessions",
        "engagementRate": "engagement_rate",
        "averageSessionDuration": "average_session_duration",
        "eventCount": "event_count",
        "keyEvents": "key_events",
        "totalUsers": "total_users",
        "eventCountPerUser": "event_count_per_user",
    }
    return all(getattr(current, field_names[name]) == row.metrics[name] for name in report.metrics)


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise GA4ConfigurationError("GA4 property returned an invalid timezone") from error


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)
