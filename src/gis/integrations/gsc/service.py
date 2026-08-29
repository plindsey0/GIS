from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.integrations.gsc.client import GSCClient
from gis.integrations.gsc.config import CollectionGrain, GSCConfigurationError, GSCConnectionConfig
from gis.models import (
    ConnectionStatus,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    GSCSearchObservation,
    IngestionRun,
    IngestionStatus,
    QualityFlag,
)

LOGGER = logging.getLogger(__name__)
GSC_REPORTING_TIMEZONE = ZoneInfo("America/Los_Angeles")


class GSCIngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizedRow:
    observation_key: str
    observed_date: date
    query: str | None
    page: str | None
    country: str | None
    device: str | None
    search_appearance: str | None
    clicks: Decimal
    impressions: Decimal
    ctr: Decimal
    position: Decimal


def validate_connection(
    connection: DataSourceConnection, source: DataSource
) -> GSCConnectionConfig:
    if source.key != "google_search_console":
        raise GSCConfigurationError("connection is not for google_search_console")
    if connection.site_id is None:
        raise GSCConfigurationError("GSC connections must be scoped to a site")
    if not connection.credential_reference:
        raise GSCConfigurationError("credential_reference is required")
    return GSCConnectionConfig.from_json(connection.configuration_json)


def date_chunks(start_date: date, end_date: date) -> list[tuple[date, date]]:
    if end_date < start_date:
        raise GSCConfigurationError("end_date must be on or after start_date")
    days = (end_date - start_date).days + 1
    return [
        (start_date + timedelta(days=offset), start_date + timedelta(days=offset))
        for offset in range(days)
    ]


def recent_window(recent_days: int, today: date | None = None) -> tuple[date, date]:
    if recent_days < 1:
        raise GSCConfigurationError("recent_days must be positive")
    current = today or datetime.now(GSC_REPORTING_TIMEZONE).date()
    end_date = current - timedelta(days=1)
    return end_date - timedelta(days=recent_days - 1), end_date


def normalize_row(
    row: dict[str, Any],
    config: GSCConnectionConfig,
    *,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    connection_id: uuid.UUID,
    requested_date: date,
) -> NormalizedRow:
    keys = row.get("keys", [])
    if not isinstance(keys, list) or len(keys) != len(config.dimensions):
        raise GSCIngestionError("row keys do not match requested dimensions")
    values = dict(zip(config.dimensions, keys))
    try:
        observed_date = date.fromisoformat(str(values.get("date")))
    except ValueError as error:
        raise GSCIngestionError("row has invalid date") from error
    if observed_date != requested_date:
        raise GSCIngestionError("row date does not match requested chunk")
    dimensions = {
        name: _dimension(values.get(name))
        for name in ("query", "page", "country", "device", "searchAppearance")
    }
    if dimensions["page"] is None:
        raise GSCIngestionError("page dimension is required")
    metrics = {
        name: _metric(row.get(name), name) for name in ("clicks", "impressions", "ctr", "position")
    }
    identity = [
        str(tenant_id),
        str(site_id),
        str(connection_id),
        observed_date.isoformat(),
        config.search_type,
        config.collection_grain.value,
        dimensions["query"],
        dimensions["page"],
        dimensions["country"],
        dimensions["device"],
        dimensions["searchAppearance"],
    ]
    observation_key = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return NormalizedRow(
        observation_key=observation_key,
        observed_date=observed_date,
        query=dimensions["query"],
        page=dimensions["page"],
        country=dimensions["country"],
        device=dimensions["device"],
        search_appearance=dimensions["searchAppearance"],
        clicks=metrics["clicks"],
        impressions=metrics["impressions"],
        ctr=metrics["ctr"],
        position=metrics["position"],
    )


class GSCCollector:
    def __init__(self, session: Session, client: GSCClient) -> None:
        self.session = session
        self.client = client

    def sync(
        self,
        connection_id: uuid.UUID,
        start_date: date,
        end_date: date,
        *,
        grain: CollectionGrain | None = None,
        search_type: str | None = None,
        dry_run: bool = False,
    ) -> IngestionRun:
        connection, source = self._connection(connection_id)
        config = validate_connection(connection, source)
        if connection.status is not ConnectionStatus.ACTIVE:
            raise GSCConfigurationError("connection must be ACTIVE; run validate first")
        if grain is not None:
            config = replace(config, collection_grain=grain)
        if search_type is not None:
            config = GSCConnectionConfig.from_json({**config.as_json(), "search_type": search_type})
        rights_policy_id = connection.rights_policy_id or source.default_rights_policy_id
        if rights_policy_id is None or self.session.get(DataRightsPolicy, rights_policy_id) is None:
            raise GSCConfigurationError("no applicable data-rights policy")
        assert connection.site_id is not None
        run = self._start_run(connection)
        completed_chunks = 0
        for chunk_start, chunk_end in date_chunks(start_date, end_date):
            try:
                rows = list(self.client.iter_rows(config, chunk_start, chunk_end))
                received, inserted, rejected = self._persist_chunk(
                    run,
                    connection,
                    config,
                    rights_policy_id,
                    chunk_start,
                    rows,
                    dry_run=dry_run,
                )
                run.records_received += received
                run.records_inserted += inserted
                run.records_rejected += rejected
                run.error_count += rejected
                if rejected:
                    run.error_summary = f"{rejected} malformed provider row(s) rejected"
                run.source_cursor = chunk_end.isoformat()
                connection.last_attempted_sync_at = _now()
                self.session.commit()
                completed_chunks += 1
                LOGGER.info(
                    "gsc_chunk_complete",
                    extra={
                        "connection_id": str(connection.id),
                        "site_id": str(connection.site_id),
                        "run_id": str(run.id),
                        "property_uri": config.property_uri,
                        "date": chunk_start.isoformat(),
                        "grain": config.collection_grain.value,
                        "rows": received,
                    },
                )
            except Exception as error:
                self.session.rollback()
                refreshed_run = self.session.get(IngestionRun, run.id)
                if refreshed_run is None:
                    raise GSCIngestionError("ingestion run disappeared") from error
                run = refreshed_run
                run.status = IngestionStatus.PARTIAL if completed_chunks else IngestionStatus.FAILED
                run.completed_at = _now()
                run.error_count += 1
                run.error_summary = f"{chunk_start.isoformat()}: {type(error).__name__}: {error}"
                self.session.commit()
                LOGGER.exception(
                    "gsc_chunk_failed",
                    extra={
                        "connection_id": str(connection_id),
                        "run_id": str(run.id),
                        "date": chunk_start.isoformat(),
                    },
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
            raise GSCConfigurationError("connection not found")
        source = self.session.get(DataSource, connection.data_source_id)
        if source is None:
            raise GSCConfigurationError("connection source not found")
        return connection, source

    def _start_run(self, connection: DataSourceConnection) -> IngestionRun:
        run = IngestionRun(
            tenant_id=connection.tenant_id,
            site_id=connection.site_id,
            data_source_connection_id=connection.id,
            started_at=_now(),
            status=IngestionStatus.PENDING,
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
        config: GSCConnectionConfig,
        rights_policy_id: uuid.UUID,
        observed_date: date,
        rows: list[dict[str, Any]],
        *,
        dry_run: bool,
    ) -> tuple[int, int, int]:
        normalized: list[NormalizedRow] = []
        rejected = 0
        assert connection.site_id is not None
        for provider_row in rows:
            try:
                normalized.append(
                    normalize_row(
                        provider_row,
                        config,
                        tenant_id=connection.tenant_id,
                        site_id=connection.site_id,
                        connection_id=connection.id,
                        requested_date=observed_date,
                    )
                )
            except GSCIngestionError:
                rejected += 1
        if dry_run:
            return len(rows), 0, rejected
        inserted = 0
        revision_time = _now()
        for normalized_row in normalized:
            current = self.session.scalar(
                select(GSCSearchObservation)
                .where(
                    GSCSearchObservation.observation_key == normalized_row.observation_key,
                    GSCSearchObservation.effective_end.is_(None),
                )
                .with_for_update()
            )
            if current is not None and _metrics_equal(current, normalized_row):
                continue
            if current is not None:
                current.effective_end = revision_time
            observation = GSCSearchObservation(
                tenant_id=connection.tenant_id,
                site_id=connection.site_id,
                data_source_connection_id=connection.id,
                ingestion_run_id=run.id,
                rights_policy_id=rights_policy_id,
                source_record_id=normalized_row.observation_key,
                observation_key=normalized_row.observation_key,
                collection_grain=config.collection_grain.value,
                observed_date=normalized_row.observed_date,
                query=normalized_row.query,
                query_hash=_text_hash(normalized_row.query),
                page=normalized_row.page,
                page_hash=_text_hash(normalized_row.page),
                country=normalized_row.country,
                device=normalized_row.device,
                search_appearance=normalized_row.search_appearance,
                search_type=config.search_type,
                clicks=normalized_row.clicks,
                impressions=normalized_row.impressions,
                ctr=normalized_row.ctr,
                position=normalized_row.position,
                observed_at=datetime.combine(
                    normalized_row.observed_date, time.min, tzinfo=GSC_REPORTING_TIMEZONE
                ).astimezone(timezone.utc),
                effective_start=revision_time,
                quality_flag=QualityFlag.VALID,
            )
            self.session.add(observation)
            inserted += 1
        self.session.flush()
        return len(rows), inserted, rejected


def _dimension(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise GSCIngestionError("dimension value must be a string or null")
    return value


def _metric(value: Any, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise GSCIngestionError(f"{name} is not numeric") from error
    if not result.is_finite() or result < 0:
        raise GSCIngestionError(f"{name} must be finite and nonnegative")
    return result


def _metrics_equal(current: GSCSearchObservation, row: NormalizedRow) -> bool:
    return (
        current.clicks == row.clicks
        and current.impressions == row.impressions
        and current.ctr == row.ctr
        and current.position == row.position
    )


def _text_hash(value: str | None) -> str | None:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value is not None else None


def _now() -> datetime:
    return datetime.now(timezone.utc)
