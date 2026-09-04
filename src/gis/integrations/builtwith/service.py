from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from gis.integrations.builtwith.provider import ENDPOINT, Profile
from gis.integrations.external_search.dataforseo import normalize_domain
from gis.integrations.technology_intelligence.service import resolve_provider_technology
from gis.models import (
    AcquisitionMethod,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    FailureCategory,
    IngestionRun,
    IngestionStatus,
    PermittedUse,
    RightsStatus,
    Site,
    TechnologyDetection,
    TechnologyEvidence,
    TechnologyObservation,
)
from gis.orchestration.reliability import ClassifiedFailure
from gis.provenance.service import evaluate_connection_use
from gis.provider_control.service import ProviderControlService


class ProfileProvider(Protocol):
    def collect(self, domain: str) -> Profile: ...


class BuiltWithCollector:
    def __init__(self, session: Session, provider: ProfileProvider):
        self.session, self.provider = session, provider

    def sync(self, connection_id: uuid.UUID, site_id: uuid.UUID, domain: str) -> IngestionRun:
        if os.environ.get("GIS_PAID_EXECUTION_DISABLED") == "1":
            raise ClassifiedFailure(FailureCategory.CONFIGURATION_ERROR, "Paid execution is held")
        domain = normalize_domain(domain)
        connection = self.session.get(DataSourceConnection, connection_id)
        site = self.session.get(Site, site_id)
        source = self.session.get(DataSource, connection.data_source_id) if connection else None
        if (
            not connection
            or not site
            or not source
            or source.key != "builtwith"
            or connection.tenant_id != site.tenant_id
            or connection.site_id not in {None, site.id}
        ):
            raise ValueError("BuiltWith connection/site scope mismatch")
        for use in (PermittedUse.NORMALIZED_RETENTION, PermittedUse.RAW_RETENTION):
            if (
                evaluate_connection_use(self.session, connection, use).status
                != RightsStatus.ALLOWED
            ):
                raise ClassifiedFailure(
                    FailureCategory.RIGHTS_BLOCKED,
                    "BuiltWith requires reviewed raw and normalized retention rights",
                )
        rights = self.session.get(
            DataRightsPolicy, connection.rights_policy_id or source.default_rights_policy_id
        )
        assert rights is not None
        control = ProviderControlService(self.session)
        policy = control.policy(
            site.tenant_id, site.id, control.provider("builtwith").id, lock=True
        )
        if not policy or policy.data_source_connection_id != connection.id:
            raise ValueError("BuiltWith must use the policy connection")
        check = control.preflight(
            site.tenant_id,
            site.id,
            "builtwith",
            "TECHNOLOGY_PROFILE",
            [domain],
            1,
            Decimal(1),
            reserve=True,
        )
        if not check.can_execute or not check.reservation_id:
            raise ClassifiedFailure(
                FailureCategory.BUDGET_BLOCKED,
                "BuiltWith blocked: " + ", ".join(check.blocking_reasons),
            )
        now = datetime.now(timezone.utc)
        run = IngestionRun(
            tenant_id=site.tenant_id,
            site_id=site.id,
            data_source_connection_id=connection.id,
            started_at=now,
            status=IngestionStatus.RUNNING,
            rights_policy_id=rights.id,
            acquisition_method=AcquisitionMethod.LICENSED_API,
            collector_name="gis.integrations.builtwith",
            collector_version="1",
            schema_version="v23",
            source_metadata={
                "target_domain": domain,
                "endpoint": ENDPOINT,
                "capability": "TECHNOLOGY_PROFILE",
            },
        )
        self.session.add(run)
        self.session.flush()
        reservation = check.reservation_id
        # Persist the reservation before dispatch; uncertain failures remain unreconciled.
        self.session.commit()
        nested = self.session.begin_nested()
        try:
            profile = self.provider.collect(domain)
            raw = json.dumps(profile.payload, sort_keys=True, default=str)
            digest = hashlib.sha256(raw.encode()).hexdigest()
            observation = TechnologyObservation(
                tenant_id=site.tenant_id,
                organization_id=site.organization_id,
                site_id=site.id,
                data_source_connection_id=connection.id,
                ingestion_run_id=run.id,
                rights_policy_id=rights.id,
                rights_policy_version=rights.policy_version,
                domain=domain,
                requested_url=f"https://{domain}/",
                normalized_url=f"https://{domain}/",
                ownership_class="OWNED"
                if urlsplit(site.canonical_url).hostname == domain
                else "COMPETITOR",
                observation_scope="DOMAIN",
                observed_at=now,
                collected_at=now,
                collection_status="SUCCESS",
                http_status=200,
                render_mode="PROVIDER_API",
                content_hash=digest,
                observation_key=hashlib.sha256(
                    f"{connection.id}:{run.id}:{domain}".encode()
                ).hexdigest(),
                request_count=1,
                estimated_cost=check.estimated_cost,
                cost_currency=check.currency,
                effective_start=now,
                collection_metadata={
                    "provider": "builtwith",
                    "endpoint": ENDPOINT,
                    "payload": profile.payload,
                    "response_headers": profile.headers,
                    "billing_credits_expected": 1,
                    "presence_semantics": "PROVIDER_REPORTED_HISTORY_NOT_CURRENT_VERIFICATION",
                },
            )
            self.session.add(observation)
            self.session.flush()
            detections: dict[uuid.UUID, TechnologyDetection] = {}
            evidence_seen: set[tuple[uuid.UUID, str]] = set()
            for item in profile.technologies:
                tech = item["technology"]
                identity = resolve_provider_technology(
                    self.session,
                    tech["Name"],
                    source_key="builtwith",
                    provider_category=str(tech.get("Tag") or "UNKNOWN"),
                    provider_identifier=str(tech["Id"]) if tech.get("Id") is not None else None,
                )
                detection = detections.get(identity.id)
                if detection is None:
                    detection = TechnologyDetection(
                        observation_id=observation.id,
                        technology_id=identity.id,
                        provider_technology_name=tech["Name"],
                        provider_category=str(tech.get("Tag") or "UNKNOWN"),
                        presence_status="UNKNOWN",
                        detection_scope="DOMAIN",
                        confidence=Decimal("1"),
                        semantic_class="PROVIDER_REPORTED",
                        detection_method="BUILTWITH_DOMAIN_API",
                        metadata_json={
                            "confidence_semantics": "faithful_provider_attribution_not_current_presence_probability"
                        },
                    )
                    self.session.add(detection)
                    self.session.flush()
                    detections[identity.id] = detection
                value = json.dumps(item, sort_keys=True, default=str)
                evidence_hash = hashlib.sha256(value.encode()).hexdigest()
                if (detection.id, evidence_hash) in evidence_seen:
                    continue
                evidence_seen.add((detection.id, evidence_hash))
                self.session.add(
                    TechnologyEvidence(
                        detection_id=detection.id,
                        signature_key=f"builtwith:{tech.get('Id', identity.slug)}"[:255],
                        signature_version="v23",
                        evidence_type="PROVIDER_PAYLOAD",
                        match_target="DOMAIN",
                        evidence_value=value,
                        evidence_hash=evidence_hash,
                        semantic_class="PROVIDER_REPORTED",
                        confidence=Decimal("1"),
                    )
                )
            run.records_received = len(profile.technologies)
            run.records_inserted = len(detections)
            run.completed_at = datetime.now(timezone.utc)
            run.status = IngestionStatus.SUCCEEDED
            run.source_metadata = {
                **run.source_metadata,
                "provider_response_validated": True,
                "payload_sha256": digest,
                "observation_id": str(observation.id),
                "response_headers": profile.headers,
                "billing_credits_expected": 1,
                "provider_cost": None,
            }
            # The API has no documented per-call dollar charge. Spend is website tech spend,
            # not our API cost. Operator unit pricing is an estimate, never actual spend.
            control.reconcile(
                reservation,
                actual_cost=None,
                semantics="UNKNOWN",
                status="SUCCEEDED",
                ingestion_run_id=run.id,
            )
            nested.commit()
        except Exception as error:
            nested.rollback()
            run.status = IngestionStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            run.error_count = 1
            run.error_summary = (
                str(error)
                if isinstance(error, ClassifiedFailure)
                else "Internal BuiltWith processing error"
            )
            control.reconcile(
                reservation,
                actual_cost=None,
                semantics="UNKNOWN",
                status="FAILED",
                ingestion_run_id=run.id,
            )
            self.session.commit()
            raise
        self.session.commit()
        return run
