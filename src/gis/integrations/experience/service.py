from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from gis.integrations.experience.pagespeed import (
    PageSpeedProvider,
    cwv_classification,
    normalize_pagespeed,
    normalize_target,
)
from gis.models import (
    ConnectionStatus,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    ExperienceObservation,
    ExperienceScope,
    FormFactor,
    IngestionRun,
    IngestionStatus,
)


class ExperienceCollector:
    def __init__(self, session: Session, provider: PageSpeedProvider) -> None:
        self.session, self.provider = session, provider

    def sync(
        self,
        connection_id: uuid.UUID,
        target: str,
        form_factor: FormFactor,
        scope: ExperienceScope = ExperienceScope.URL,
    ) -> IngestionRun:
        connection = self.session.get(DataSourceConnection, connection_id)
        source = self.session.get(DataSource, connection.data_source_id) if connection else None
        policy_id = (
            connection.rights_policy_id or (source.default_rights_policy_id if source else None)
            if connection
            else None
        )
        policy = self.session.get(DataRightsPolicy, policy_id) if policy_id else None
        if not connection or not connection.site_id or not source or not policy:
            raise ValueError("experience connection and policy are required")
        now = datetime.now(timezone.utc)
        normalized_target = normalize_target(target, scope)
        run = IngestionRun(
            tenant_id=connection.tenant_id,
            site_id=connection.site_id,
            data_source_connection_id=connection.id,
            started_at=now,
            status=IngestionStatus.RUNNING,
            rights_policy_id=policy.id,
            acquisition_method=source.acquisition_method,
            collector_name="gis.integrations.experience",
            collector_version="1",
            schema_version="1",
            source_metadata={"target": normalized_target, "form_factor": form_factor.value},
        )
        self.session.add(run)
        self.session.flush()
        try:
            payload, observed_at = self.provider.collect(normalized_target, form_factor)
            rows = normalize_pagespeed(payload, form_factor)
            for row in rows:
                self.session.add(
                    ExperienceObservation(
                        tenant_id=connection.tenant_id,
                        site_id=connection.site_id,
                        ingestion_run_id=run.id,
                        data_source_connection_id=connection.id,
                        rights_policy_id=policy.id,
                        rights_policy_version=policy.policy_version,
                        observed_at=observed_at,
                        period_end=observed_at.date(),
                        target=target,
                        normalized_target=normalized_target,
                        measurement_type=row.measurement_type,
                        scope=row.scope,
                        form_factor=row.form_factor,
                        availability=row.availability,
                        metric=row.metric,
                        metric_value=row.value,
                        unit=row.unit,
                        percentile=row.percentile,
                        classification=cwv_classification(row.metric, row.value)
                        or row.classification,
                        good_proportion=row.good,
                        needs_improvement_proportion=row.needs,
                        poor_proportion=row.poor,
                    )
                )
            run.records_received = len(rows)
            run.records_inserted = len(rows)
            run.status = IngestionStatus.SUCCEEDED
            connection.status = ConnectionStatus.ACTIVE
            connection.last_successful_sync_at = observed_at
        except Exception as error:
            run.status = IngestionStatus.FAILED
            run.error_count = 1
            run.error_summary = safe_error_summary(error)
        connection.last_attempted_sync_at = run.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        return run


def safe_error_summary(error: Exception) -> str:
    match = re.fullmatch(r"PageSpeed HTTP ([45][0-9]{2})", str(error))
    return f"PageSpeed HTTP {match.group(1)}" if match else type(error).__name__
