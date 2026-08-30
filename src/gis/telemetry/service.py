from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    CalculatorRun,
    ConnectionStatus,
    Conversion,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    ProductEvent,
    ProductSession,
    Site,
    Tenant,
)
from gis.telemetry.schemas import EventError, TelemetryBatchInput, TelemetryResponse
from gis.telemetry.validators import (
    EventValidationError,
    sanitize_path,
    sanitize_url,
    validate_event,
)


@dataclass(frozen=True)
class TelemetryContext:
    tenant: Tenant
    site: Site
    source: DataSource
    connection: DataSourceConnection
    rights_policy_id: uuid.UUID


def resolve_context(session: Session, tenant_key: str, site_key: str) -> TelemetryContext:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_key))
    if tenant is None:
        raise LookupError("telemetry site not found")
    site = session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == site_key))
    if site is None:
        raise LookupError("telemetry site not found")
    source = session.scalar(select(DataSource).where(DataSource.key == "first_party"))
    if source is None:
        raise LookupError("first_party source is not seeded")
    connection = session.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.tenant_id == tenant.id,
            DataSourceConnection.site_id == site.id,
            DataSourceConnection.data_source_id == source.id,
            DataSourceConnection.status == ConnectionStatus.ACTIVE,
        )
    )
    if connection is None:
        raise LookupError("active first-party telemetry connection not found")
    rights_id = connection.rights_policy_id or source.default_rights_policy_id
    if rights_id is None or session.get(DataRightsPolicy, rights_id) is None:
        raise LookupError("no applicable data-rights policy")
    return TelemetryContext(tenant, site, source, connection, rights_id)


class TelemetryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ingest(
        self,
        batch: TelemetryBatchInput,
        context: TelemetryContext,
        *,
        request_id: uuid.UUID | None = None,
        now: datetime | None = None,
        ingestion_run_id: uuid.UUID | None = None,
    ) -> TelemetryResponse:
        received_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        request_id = request_id or uuid.uuid4()
        accepted = duplicates = 0
        errors: list[EventError] = []
        product_session: ProductSession | None = None
        for event_input in batch.events:
            existing = self.session.scalar(
                select(ProductEvent).where(
                    ProductEvent.tenant_id == context.tenant.id,
                    ProductEvent.site_id == context.site.id,
                    ProductEvent.event_id == event_input.event_id,
                )
            )
            if existing is not None:
                duplicates += 1
                continue
            try:
                properties = validate_event(event_input, received_at)
                page_url = sanitize_url(event_input.page_url)
                page_path = sanitize_path(event_input.page_path)
                if product_session is None:
                    product_session = self._session(batch, context, event_input.occurred_at)
                calculator_run = self._calculator_run(
                    event_input.event_name,
                    properties,
                    event_input.occurred_at,
                    page_path,
                    product_session,
                    context,
                )
                event = ProductEvent(
                    tenant_id=context.tenant.id,
                    site_id=context.site.id,
                    session_id=product_session.id,
                    calculator_run_id=calculator_run.id if calculator_run else None,
                    data_source_connection_id=context.connection.id,
                    rights_policy_id=context.rights_policy_id,
                    ingestion_run_id=ingestion_run_id,
                    event_id=event_input.event_id,
                    event_name=event_input.event_name,
                    event_version=event_input.event_version,
                    occurred_at=event_input.occurred_at,
                    received_at=received_at,
                    page_url=page_url,
                    page_path=page_path,
                    event_properties=properties,
                    sequence_number=event_input.sequence_number,
                )
                self.session.add(event)
                self.session.flush()
                self._conversion(event, properties, calculator_run, context)
                accepted += 1
                product_session.last_event_at = max(
                    product_session.last_event_at, event_input.occurred_at
                )
            except EventValidationError as error:
                errors.append(EventError(event_id=event_input.event_id, code=error.code))
        self.session.commit()
        return TelemetryResponse(
            request_id=request_id,
            accepted=accepted,
            duplicates=duplicates,
            rejected=len(errors),
            errors=errors,
        )

    def _session(
        self, batch: TelemetryBatchInput, context: TelemetryContext, first_event_at: datetime
    ) -> ProductSession:
        current = self.session.scalar(
            select(ProductSession).where(
                ProductSession.tenant_id == context.tenant.id,
                ProductSession.site_id == context.site.id,
                ProductSession.session_key == batch.session_key,
            )
        )
        if current is not None:
            return current
        landing_url = sanitize_url(batch.landing_url)
        referrer_url = sanitize_url(batch.referrer_url)
        current = ProductSession(
            tenant_id=context.tenant.id,
            site_id=context.site.id,
            data_source_connection_id=context.connection.id,
            rights_policy_id=context.rights_policy_id,
            session_key=batch.session_key,
            started_at=first_event_at,
            last_event_at=first_event_at,
            landing_url=landing_url,
            landing_path=urlsplit(landing_url).path if landing_url else None,
            referrer_url=referrer_url,
            initial_referrer_domain=urlsplit(referrer_url).hostname if referrer_url else None,
            initial_utm_source=batch.utm_source,
            initial_utm_medium=batch.utm_medium,
            initial_utm_campaign=batch.utm_campaign,
            initial_utm_term=batch.utm_term,
            initial_utm_content=batch.utm_content,
            initial_gclid=batch.gclid,
            initial_msclkid=batch.msclkid,
            device_category=batch.device_category,
            browser_family=batch.browser_family,
            os_family=batch.os_family,
            country_code=batch.country_code,
            region_code=batch.region_code,
            anonymous_visitor_key=batch.anonymous_visitor_key,
        )
        self.session.add(current)
        self.session.flush()
        return current

    def _calculator_run(
        self,
        event_name: str,
        properties: dict[str, Any],
        occurred_at: datetime,
        page_path: str | None,
        product_session: ProductSession,
        context: TelemetryContext,
    ) -> CalculatorRun | None:
        raw_key = properties.get("calculator_run_key")
        if raw_key is None:
            return None
        run_key = uuid.UUID(str(raw_key))
        run = self.session.scalar(
            select(CalculatorRun).where(
                CalculatorRun.tenant_id == context.tenant.id,
                CalculatorRun.site_id == context.site.id,
                CalculatorRun.calculator_run_key == run_key,
            )
        )
        if run is None:
            if event_name != "calculator_start":
                raise EventValidationError("INVALID_CALCULATOR_RUN")
            bucket_data = _bucket_data(properties)
            run = CalculatorRun(
                tenant_id=context.tenant.id,
                site_id=context.site.id,
                session_id=product_session.id,
                data_source_connection_id=context.connection.id,
                rights_policy_id=context.rights_policy_id,
                calculator_run_key=run_key,
                calculator_type=str(properties["calculator_type"]),
                started_at=occurred_at,
                initial_page_path=page_path,
                input_schema_version=str(properties["input_schema_version"]),
                input_bucket_data=bucket_data,
            )
            self.session.add(run)
            self.session.flush()
        elif run.session_id != product_session.id:
            raise EventValidationError("INVALID_CALCULATOR_RUN")
        if event_name == "calculator_recalculate":
            run.recalculation_count += 1
            run.input_bucket_data = _bucket_data(properties)
        elif event_name == "calculator_complete":
            run.completed_at = occurred_at
            run.result_schema_version = str(properties["result_schema_version"])
            run.result_bucket_data = _bucket_data(properties)
        return run

    def _conversion(
        self,
        event: ProductEvent,
        properties: dict[str, Any],
        calculator_run: CalculatorRun | None,
        context: TelemetryContext,
    ) -> None:
        conversion_type: str | None = None
        conversion_id = event.event_id
        value: Decimal | None = None
        currency: str | None = None
        if event.event_name == "lead_form_complete":
            conversion_type = "lead"
        elif event.event_name == "conversion":
            conversion_type = str(properties["conversion_type"])
            conversion_id = uuid.UUID(str(properties.get("conversion_id", event.event_id)))
            if "conversion_value" in properties:
                try:
                    value = Decimal(str(properties["conversion_value"]))
                except InvalidOperation as error:
                    raise EventValidationError("INVALID_EVENT_PROPERTIES") from error
                if not value.is_finite() or value < 0:
                    raise EventValidationError("INVALID_EVENT_PROPERTIES")
            currency = str(properties["currency"]) if "currency" in properties else None
            if currency is not None and (len(currency) != 3 or not currency.isalpha()):
                raise EventValidationError("INVALID_EVENT_PROPERTIES")
        if conversion_type is None:
            return
        self.session.add(
            Conversion(
                tenant_id=context.tenant.id,
                site_id=context.site.id,
                session_id=event.session_id,
                calculator_run_id=calculator_run.id if calculator_run else None,
                data_source_connection_id=context.connection.id,
                rights_policy_id=context.rights_policy_id,
                conversion_id=conversion_id,
                conversion_type=conversion_type,
                occurred_at=event.occurred_at,
                source_event_id=event.id,
                conversion_value=value,
                currency=currency.upper() if currency else None,
                metadata_json={},
            )
        )


def _bucket_data(properties: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "calculator_run_key",
        "calculator_type",
        "input_schema_version",
        "result_schema_version",
    }
    return {key: value for key, value in properties.items() if key not in excluded}
