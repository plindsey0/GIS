from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    AnalyticalEntity,
    AssetLayer,
    AssetType,
    DemandEvidenceStrength,
    ExpectedDirection,
    FeasibilityState,
    Intervention,
    InterventionFamily,
    InterventionHypothesis,
    InterventionLifecycleEvent,
    InterventionStatus,
    InterventionTypeDefinition,
    MeasurementContract,
    MeasurementMetric,
    MeasurementReadiness,
    MetricDefinition,
    MetricRole,
    Opportunity,
)
from gis.provenance.lineage import register_asset, register_lineage

VERSION = "INTERVENTION_CONTRACT_V1"

TYPES: dict[str, dict[str, Any]] = {
    "UPDATE_CONTENT_ASSET": {"family": InterventionFamily.CONTENT, "entities": ["URL"], "parameters": ["target_url", "content_scope"], "metrics": ["GSC_CLICKS", "GSC_CTR", "GA4_SESSIONS"], "execution_mode": "MANUAL"},
    "CHANGE_PAGE_METADATA": {"family": InterventionFamily.SEO, "entities": ["URL"], "parameters": ["target_url", "metadata_scope"], "metrics": ["GSC_CLICKS", "GSC_CTR", "GSC_POSITION"], "execution_mode": "MANUAL"},
    "IMPROVE_PAGE_EXPERIENCE": {"family": InterventionFamily.EXPERIENCE, "entities": ["URL"], "parameters": ["target_url", "experience_scope"], "metrics": ["CRUX_LCP", "CRUX_INP", "CRUX_CLS"], "execution_mode": "MANUAL"},
    "CHANGE_CTA": {"family": InterventionFamily.CONVERSION, "entities": ["URL"], "parameters": ["target_url", "cta_identifier"], "metrics": ["TELEMETRY_CTA_INTERACTION", "TELEMETRY_CONVERSION"], "execution_mode": "MANUAL"},
    "EXPAND_COLLECTION": {"family": InterventionFamily.COLLECTION, "entities": ["QUERY", "TOPIC", "URL", "DOMAIN", "MARKET", "MARKET_SEGMENT"], "parameters": ["requested_evidence_type"], "metrics": ["EVIDENCE_SUFFICIENCY"], "execution_mode": "ASSISTED"},
}

METRICS: dict[str, tuple[str, str, str]] = {
    "GSC_CLICKS": ("Google Search Console clicks", "google_search_console", "count"),
    "GSC_CTR": ("Google Search Console CTR", "google_search_console", "ratio"),
    "GSC_POSITION": ("Google Search Console average position", "google_search_console", "position"),
    "GA4_SESSIONS": ("GA4 sessions", "ga4", "count"),
    "TELEMETRY_CTA_INTERACTION": ("First-party CTA interactions", "first_party", "count"),
    "TELEMETRY_CONVERSION": ("First-party conversions", "first_party", "count"),
    "CRUX_LCP": ("CrUX LCP", "pagespeed", "milliseconds"),
    "CRUX_INP": ("CrUX INP", "pagespeed", "milliseconds"),
    "CRUX_CLS": ("CrUX CLS", "pagespeed", "score"),
    "EVIDENCE_SUFFICIENCY": ("Evidence sufficiency", "gis", "category"),
}

TRANSITIONS: dict[InterventionStatus, set[InterventionStatus]] = {
    InterventionStatus.DRAFT: {InterventionStatus.PROPOSED, InterventionStatus.CANCELLED},
    InterventionStatus.PROPOSED: {InterventionStatus.APPROVED, InterventionStatus.REJECTED, InterventionStatus.CANCELLED},
    InterventionStatus.APPROVED: {InterventionStatus.SCHEDULED, InterventionStatus.IN_PROGRESS, InterventionStatus.CANCELLED},
    InterventionStatus.SCHEDULED: {InterventionStatus.IN_PROGRESS, InterventionStatus.CANCELLED},
    InterventionStatus.IN_PROGRESS: {InterventionStatus.COMPLETED, InterventionStatus.CANCELLED},
    InterventionStatus.COMPLETED: {InterventionStatus.MEASURING, InterventionStatus.ARCHIVED},
    InterventionStatus.MEASURING: {InterventionStatus.MEASURED, InterventionStatus.ARCHIVED},
    InterventionStatus.MEASURED: {InterventionStatus.ARCHIVED},
    InterventionStatus.REJECTED: {InterventionStatus.ARCHIVED},
    InterventionStatus.CANCELLED: {InterventionStatus.ARCHIVED},
}


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class InterventionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_registry(self) -> tuple[dict[str, InterventionTypeDefinition], dict[str, MetricDefinition]]:
        types: dict[str, InterventionTypeDefinition] = {}
        metrics: dict[str, MetricDefinition] = {}
        for key, spec in TYPES.items():
            type_row = self.session.scalar(select(InterventionTypeDefinition).where(InterventionTypeDefinition.key == key, InterventionTypeDefinition.version == VERSION))
            if not type_row:
                type_row = InterventionTypeDefinition(key=key, version=VERSION, name=key.replace("_", " ").title(), description=f"Structured {key.casefold().replace('_', ' ')} contract.", family=spec["family"], execution_mode=spec["execution_mode"], autonomy_level="HUMAN_APPROVAL_REQUIRED", enabled=True, schema_json={"applicable_entities": spec["entities"], "required_parameters": spec["parameters"], "supported_metrics": spec["metrics"], "measurement_required": True})
                self.session.add(type_row)
                self.session.flush()
            types[key] = type_row
        for key, (name, source, unit) in METRICS.items():
            metric_row = self.session.scalar(select(MetricDefinition).where(MetricDefinition.key == key, MetricDefinition.version == VERSION))
            if not metric_row:
                metric_row = MetricDefinition(key=key, version=VERSION, name=name, source_system=source, unit=unit, grain="ANALYTICAL_ENTITY_PERIOD", enabled=True)
                self.session.add(metric_row)
                self.session.flush()
            metrics[key] = metric_row
        return types, metrics

    def ensure_lineage(self) -> None:
        opportunity = register_asset(self.session, "gis_core.opportunity", AssetType.TABLE, AssetLayer.CORE)
        intervention = register_asset(self.session, "gis_core.intervention", AssetType.TABLE, AssetLayer.CORE)
        execution = register_asset(self.session, "gis_core.intervention_execution", AssetType.EVIDENCE, AssetLayer.CORE)
        outcome = register_asset(self.session, "gis_core.intervention_outcome", AssetType.EVIDENCE, AssetLayer.CORE)
        register_lineage(self.session, opportunity, intervention, reference=VERSION)
        register_lineage(self.session, intervention, execution, reference=VERSION)
        register_lineage(self.session, execution, outcome, reference=VERSION)

    def valid_types(self, opportunity: Opportunity) -> list[dict[str, Any]]:
        entity = self.session.get(AnalyticalEntity, opportunity.analytical_entity_id)
        if not entity:
            return []
        return [{"key": key, **spec} for key, spec in TYPES.items() if entity.entity_type.value in spec["entities"]]

    def validate(self, opportunity: Opportunity, type_key: str, parameters: dict[str, Any], metric_key: str, baseline_start: datetime, baseline_end: datetime, measurement_start: datetime, measurement_end: datetime) -> list[str]:
        errors: list[str] = []
        spec = TYPES.get(type_key)
        entity = self.session.get(AnalyticalEntity, opportunity.analytical_entity_id)
        if not spec:
            return ["INTERVENTION_TYPE_UNKNOWN"]
        if not entity or entity.entity_type.value not in spec["entities"]:
            errors.append("ENTITY_TYPE_INCOMPATIBLE")
        errors.extend(f"MISSING_PARAMETER:{key}" for key in spec["parameters"] if not parameters.get(key))
        if metric_key not in spec["metrics"]:
            errors.append("METRIC_UNSUPPORTED")
        if baseline_start >= baseline_end:
            errors.append("BASELINE_WINDOW_INVALID")
        if measurement_start >= measurement_end or measurement_start <= baseline_end:
            errors.append("MEASUREMENT_WINDOW_INVALID")
        return errors

    def create(self, opportunity_id: uuid.UUID, type_key: str, parameters: dict[str, Any], metric_key: str, direction: ExpectedDirection, baseline_start: datetime, baseline_end: datetime, measurement_start: datetime, measurement_end: datetime, rationale: str, *, proposed_by: str | None = None, dry_run: bool = False) -> Intervention:
        opportunity = self.session.get(Opportunity, opportunity_id)
        if not opportunity:
            raise ValueError("opportunity not found")
        errors = self.validate(opportunity, type_key, parameters, metric_key, baseline_start, baseline_end, measurement_start, measurement_end)
        if errors:
            raise ValueError(",".join(errors))
        types, metrics = self.ensure_registry()
        self.ensure_lineage()
        identity = digest({"opportunity": opportunity.id, "type": type_key, "version": VERSION, "entity": opportunity.analytical_entity_id, "parameters": parameters})
        existing = self.session.scalar(select(Intervention).where(Intervention.identity_hash == identity))
        if existing:
            return existing
        row = Intervention(tenant_id=opportunity.tenant_id, site_id=opportunity.site_id, primary_opportunity_id=opportunity.id, analytical_entity_id=opportunity.analytical_entity_id, intervention_type_id=types[type_key].id, market_definition_id=opportunity.market_definition_id, market_definition_version=opportunity.market_definition_version, status=InterventionStatus.DRAFT, feasibility=FeasibilityState.UNKNOWN, measurement_readiness=MeasurementReadiness.PARTIAL, title=f"{types[type_key].name}: {opportunity.title}", parameters_json=parameters, constraints_json=[], risk_json=[], proposed_by=proposed_by, identity_hash=identity)
        self.session.add(row)
        self.session.flush()
        self.session.add(InterventionHypothesis(intervention_id=row.id, target_metric_key=metric_key, expected_direction=direction, target_entity_id=row.analytical_entity_id, rationale=rationale))
        contract = MeasurementContract(intervention_id=row.id, version=VERSION, baseline_strategy="FIXED_PRE_PERIOD", baseline_start=baseline_start, baseline_end=baseline_end, measurement_start=measurement_start, measurement_end=measurement_end, washout_days=max(0, (measurement_start - baseline_end).days), comparison_method="BEFORE_AFTER", minimum_evidence=DemandEvidenceStrength.SUPPORTED, freshness_days=14, exclusions_json=[], method_version=VERSION)
        self.session.add(contract)
        self.session.flush()
        self.session.add(MeasurementMetric(measurement_contract_id=contract.id, metric_definition_id=metrics[metric_key].id, role=MetricRole.PRIMARY, expected_direction=direction))
        self.session.add(InterventionLifecycleEvent(intervention_id=row.id, to_status=InterventionStatus.DRAFT, actor=proposed_by, reason="structured intervention created", occurred_at=datetime.now(timezone.utc)))
        if dry_run:
            self.session.flush()
        return row

    def transition(self, intervention_id: uuid.UUID, target: InterventionStatus, *, actor: str | None, reason: str | None = None) -> Intervention:
        row = self.session.get(Intervention, intervention_id)
        if not row:
            raise ValueError("intervention not found")
        if row.status is target:
            return row
        if target not in TRANSITIONS.get(row.status, set()):
            raise ValueError(f"invalid transition {row.status.value}->{target.value}")
        if target is InterventionStatus.APPROVED and not actor:
            raise ValueError("approval requires actor")
        previous = row.status
        row.status = target
        self.session.add(InterventionLifecycleEvent(intervention_id=row.id, from_status=previous, to_status=target, actor=actor, reason=reason, occurred_at=datetime.now(timezone.utc)))
        return row

    def baseline(self, intervention_id: uuid.UUID) -> dict[str, Any]:
        row = self.session.get(Intervention, intervention_id)
        if not row:
            raise ValueError("intervention not found")
        contract = self.session.scalar(select(MeasurementContract).where(MeasurementContract.intervention_id == row.id).order_by(MeasurementContract.created_at.desc()))
        return {"intervention_id": row.id, "contract_id": contract.id if contract else None, "status": "INSUFFICIENT_BASELINE", "value": None, "provider_calls": 0, "causal_attribution": False}

    def list(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> list[Intervention]:
        return list(self.session.scalars(select(Intervention).where(Intervention.tenant_id == tenant_id, Intervention.site_id == site_id).order_by(Intervention.created_at.desc())))
