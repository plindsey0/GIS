from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_CEILING, Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    DataRightsPolicy,
    DecompositionPlan,
    DecompositionPlanStatus,
    DecompositionRule,
    DecompositionState,
    DerivationResultStatus,
    MetricDefinition,
    ObjectiveApproval,
    ObjectiveAuditEvent,
    ObjectiveDerivation,
    ObjectiveFeasibility,
    ObjectiveLevel,
    ObjectiveLifecycle,
    ObjectiveMeasurement,
    ObjectiveMeasurementHealth,
    ObjectiveOrigin,
    ObjectiveProgress,
    ObjectiveRelationship,
    ObjectiveRelationshipType,
    ObjectiveTarget,
    ObjectiveType,
    RightsDecision,
    StrategicObjective,
    TargetDirection,
    TargetFamily,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


METRICS: dict[str, dict[str, Any]] = {
    "GSC_IMPRESSIONS": {
        "name": "GSC impressions",
        "source": "GSC",
        "unit": "count",
        "domain": "SEARCH",
        "aggregation": "SUM",
        "scopes": ["SITE", "QUERY", "URL"],
        "measurable": True,
    },
    "GSC_CLICKS": {
        "name": "GSC clicks",
        "source": "GSC",
        "unit": "count",
        "domain": "SEARCH",
        "aggregation": "SUM",
        "scopes": ["SITE", "QUERY", "URL"],
        "measurable": True,
    },
    "GSC_CTR": {
        "name": "Organic click-through rate",
        "source": "GSC",
        "unit": "ratio",
        "domain": "SEARCH",
        "aggregation": "WEIGHTED_RATE",
        "scopes": ["SITE", "QUERY", "URL"],
        "measurable": True,
    },
    "GSC_POSITION": {
        "name": "GSC average position",
        "source": "GSC",
        "unit": "rank",
        "domain": "SEARCH",
        "aggregation": "WEIGHTED_AVERAGE",
        "scopes": ["QUERY", "URL"],
        "measurable": True,
    },
    "GA4_SESSIONS": {
        "name": "GA4 sessions",
        "source": "GA4",
        "unit": "count",
        "domain": "TRAFFIC",
        "aggregation": "SUM",
        "scopes": ["SITE", "CHANNEL", "URL"],
        "measurable": True,
    },
    "GA4_USERS": {
        "name": "GA4 users",
        "source": "GA4",
        "unit": "count",
        "domain": "TRAFFIC",
        "aggregation": "SUM",
        "scopes": ["SITE", "CHANNEL"],
        "measurable": True,
    },
    "QUERY_RANK": {
        "name": "Observed query rank",
        "source": "SERP",
        "unit": "rank",
        "domain": "SEARCH",
        "aggregation": "LATEST",
        "scopes": ["QUERY", "URL"],
        "measurable": True,
    },
    "SEARCH_VISIBILITY_SHARE": {
        "name": "Search visibility share",
        "source": "MARKET_INTELLIGENCE",
        "unit": "ratio",
        "domain": "MARKET",
        "aggregation": "MODEL",
        "scopes": ["MARKET", "DOMAIN"],
        "measurable": True,
    },
    "CRUX_LCP": {
        "name": "Largest Contentful Paint",
        "source": "CRUX",
        "unit": "milliseconds",
        "domain": "EXPERIENCE",
        "aggregation": "P75",
        "scopes": ["SITE", "URL"],
        "measurable": False,
    },
    "MONTHLY_REVENUE": {
        "name": "Monthly revenue",
        "source": "FINANCIAL",
        "unit": "currency",
        "domain": "FINANCIAL",
        "aggregation": "SUM",
        "scopes": ["SITE"],
        "measurable": False,
    },
    "REVENUE_PER_VISITOR": {
        "name": "Revenue per qualified visitor",
        "source": "FINANCIAL",
        "unit": "currency_per_visitor",
        "domain": "FINANCIAL",
        "aggregation": "RATIO",
        "scopes": ["SITE"],
        "measurable": False,
    },
    "REQUIRED_QUALIFIED_VISITORS": {
        "name": "Required qualified visitors",
        "source": "GIS_DETERMINISTIC",
        "unit": "visitors",
        "domain": "TRAFFIC",
        "aggregation": "SUM",
        "scopes": ["SITE", "CHANNEL"],
        "measurable": False,
        "derived": True,
    },
}

SOURCE_LABELS = {
    "GSC": "Google Search Console",
    "GA4": "Google Analytics 4",
    "SERP": "SERP observations",
    "MARKET_INTELLIGENCE": "GIS market intelligence",
    "CRUX": "Chrome UX Report",
    "FINANCIAL": "First-party financial data",
    "GIS_DETERMINISTIC": "GIS deterministic analysis",
}

METRIC_DISPLAY_NAMES = {
    "GSC_IMPRESSIONS": "Search impressions",
    "GSC_CLICKS": "Search clicks",
    "GSC_CTR": "Organic click-through rate",
    "GSC_POSITION": "Average search position",
    "GA4_SESSIONS": "Website sessions",
    "GA4_USERS": "Website users",
    "QUERY_RANK": "Query rank",
}

RECOMMENDATION_POLICY_VERSION = "goal-metric-policy-v1"
GOAL_METRIC_POLICY: dict[str, list[tuple[str, str]]] = {
    "GROWTH": [
        ("GA4_SESSIONS", "Measures visits and is a direct indicator of audience activity."),
        ("GA4_USERS", "Measures the number of people using the site."),
        ("GSC_CLICKS", "Measures visits earned directly from Google Search."),
        ("GSC_IMPRESSIONS", "Measures how often the site appears in Google Search."),
    ],
    "CUSTOMER_ACQUISITION": [
        ("GA4_USERS", "Tracks people reached while a customer conversion measure is unavailable."),
        (
            "GA4_SESSIONS",
            "Tracks qualified traffic while a customer conversion measure is unavailable.",
        ),
    ],
    "LEAD_GENERATION": [
        (
            "GA4_SESSIONS",
            "Tracks traffic that can lead to inquiries while a lead measure is unavailable.",
        ),
        ("GSC_CLICKS", "Tracks visits earned from search while a lead measure is unavailable."),
    ],
    "USAGE": [
        ("GA4_USERS", "Measures the people actively using the site."),
        ("GA4_SESSIONS", "Measures repeat activity on the site."),
    ],
    "MARKET_POSITION": [
        ("SEARCH_VISIBILITY_SHARE", "Measures visibility relative to the defined search market."),
        ("QUERY_RANK", "Measures position for an individual tracked query."),
        ("GSC_IMPRESSIONS", "Measures the site's exposure in Google Search."),
    ],
    "RETENTION": [
        ("GA4_USERS", "Provides an audience measure, but does not by itself prove retention.")
    ],
    "EFFICIENCY": [("GSC_CTR", "Measures how efficiently search visibility becomes visits.")],
    "REVENUE": [("MONTHLY_REVENUE", "Directly measures money generated in a month.")],
    "PROFITABILITY": [],
    "CUSTOM": [],
}


class GoalService:
    def __init__(self, session: Session):
        self.session = session

    def ensure_registry(self) -> dict[str, MetricDefinition]:
        rows: dict[str, MetricDefinition] = {}
        for key, spec in METRICS.items():
            row = self.session.scalar(
                select(MetricDefinition).where(
                    MetricDefinition.key == key, MetricDefinition.version == "1"
                )
            )
            if row is None:
                row = MetricDefinition(
                    key=key,
                    version="1",
                    name=spec["name"],
                    source_system=spec["source"],
                    unit=spec["unit"],
                    grain="objective_window",
                    enabled=True,
                )
                self.session.add(row)
            row.description = f"Governed objective metric: {spec['name']}."
            row.domain = spec["domain"]
            row.directionality = (
                "LOWER_IS_BETTER"
                if spec["unit"] in {"rank", "milliseconds"}
                else "HIGHER_IS_BETTER"
            )
            row.aggregation = spec["aggregation"]
            row.supported_scopes_json = spec["scopes"]
            row.currently_measurable = bool(spec["measurable"])
            row.derived = bool(spec.get("derived", False))
            rows[key] = row
        rule = self.session.scalar(
            select(DecompositionRule).where(
                DecompositionRule.key == "REVENUE_TO_REQUIRED_TRAFFIC",
                DecompositionRule.version == "1",
            )
        )
        if rule is None:
            rule = DecompositionRule(
                key="REVENUE_TO_REQUIRED_TRAFFIC",
                version="1",
                name="Revenue to required qualified traffic",
                description="Divides an explicit monthly revenue target by an authoritative revenue-per-qualified-visitor measurement.",
                parent_level=ObjectiveLevel.BUSINESS,
                parent_type=ObjectiveType.REVENUE,
                output_level=ObjectiveLevel.STRATEGIC_GROWTH,
                output_type=ObjectiveType.GROWTH,
                formula="monthly_revenue_target / revenue_per_qualified_visitor",
                required_metrics_json=["MONTHLY_REVENUE", "REVENUE_PER_VISITOR"],
                supported_units_json=["currency", "currency_per_visitor", "visitors"],
                output_metric_key="REQUIRED_QUALIFIED_VISITORS",
                assumptions_json=[],
                readiness_policy_json={"require_current": True, "stale_inputs_allowed": False},
                rights_requirements_json=[
                    "deterministic_analysis_allowed",
                    "derived_storage_allowed",
                ],
                approval_required=True,
                enabled=True,
            )
            self.session.add(rule)
        self.session.flush()
        return rows

    def recommend_metrics(self, objective_type: ObjectiveType) -> dict[str, Any]:
        """Return explainable planning choices; this never creates an objective or target."""
        metrics = self.ensure_registry()
        policy = GOAL_METRIC_POLICY.get(objective_type.value, [])
        recommended: list[dict[str, Any]] = []
        policy_keys = {key for key, _ in policy}
        for rank, (key, reason) in enumerate(policy, start=1):
            metric = metrics[key]
            if metric.currently_measurable and not metric.derived:
                recommended.append(self.metric_choice(metric, reason=reason, rank=rank))
        available = [
            self.metric_choice(metric)
            for key, metric in metrics.items()
            if metric.currently_measurable and not metric.derived and key not in policy_keys
        ]
        return {
            "goal_type": objective_type.value,
            "policy_version": RECOMMENDATION_POLICY_VERSION,
            "method": "DETERMINISTIC_POLICY",
            "recommended": recommended,
            "available": sorted(available, key=lambda item: (item["domain"], item["name"])),
            "explanation": (
                "Recommendations use the selected business outcome and GIS measurement registry. "
                "They are measurement choices, not forecasts or strategic decompositions."
            ),
        }

    @staticmethod
    def metric_choice(
        metric: MetricDefinition, *, reason: Optional[str] = None, rank: Optional[int] = None
    ) -> dict[str, Any]:
        return {
            "id": str(metric.id),
            "key": metric.key,
            "name": METRIC_DISPLAY_NAMES.get(metric.key, metric.name),
            "description": metric.description,
            "domain": metric.domain,
            "unit": metric.unit,
            "directionality": metric.directionality,
            "authoritative_source": metric.source_system,
            "source_name": SOURCE_LABELS.get(metric.source_system, metric.source_system),
            "metric_capability": "SUPPORTED" if metric.currently_measurable else "UNSUPPORTED",
            "currently_measurable": metric.currently_measurable,
            "derived": metric.derived,
            "recommendation_rank": rank,
            "recommendation_reason": reason,
            "target_suggestion_policy": (
                "PERCENTAGE_PLANNING_OPTIONS"
                if metric.unit in {"count", "visitors", "currency"}
                and metric.directionality == "HIGHER_IS_BETTER"
                else "CUSTOM_ONLY"
            ),
        }

    def _objective(
        self, objective_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
    ) -> StrategicObjective:
        row = self.session.scalar(
            select(StrategicObjective).where(
                StrategicObjective.id == objective_id,
                StrategicObjective.tenant_id == tenant_id,
                StrategicObjective.site_id == site_id,
            )
        )
        if row is None:
            raise ValueError("objective not found in tenant/site scope")
        return row

    def _audit(
        self,
        row: StrategicObjective,
        event: str,
        actor: str,
        *,
        reason: Optional[str] = None,
        before: Optional[dict[str, Any]] = None,
        after: Optional[dict[str, Any]] = None,
    ) -> None:
        self.session.add(
            ObjectiveAuditEvent(
                tenant_id=row.tenant_id,
                objective_id=row.id,
                event_type=event,
                actor=actor,
                reason=reason,
                before_json=before or {},
                after_json=after or {},
                occurred_at=utcnow(),
            )
        )

    def create_goal(
        self,
        *,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        name: str,
        objective_type: ObjectiveType,
        actor: str,
        description: Optional[str] = None,
        rationale: Optional[str] = None,
        priority: str = "MEDIUM",
        deadline: Optional[date] = None,
        activate: bool = False,
    ) -> StrategicObjective:
        row = StrategicObjective(
            tenant_id=tenant_id,
            site_id=site_id,
            name=name,
            description=description,
            level=ObjectiveLevel.BUSINESS,
            objective_type=objective_type,
            lifecycle=ObjectiveLifecycle.ACTIVE if activate else ObjectiveLifecycle.DRAFT,
            origin=ObjectiveOrigin.USER_DEFINED,
            approval_state=ObjectiveApproval.NOT_REQUIRED,
            progress_state=ObjectiveProgress.UNKNOWN,
            measurement_health=ObjectiveMeasurementHealth.NOT_YET_MEASURABLE,
            decomposition_state=DecompositionState.NOT_STARTED,
            feasibility_state=ObjectiveFeasibility.NOT_ASSESSED,
            priority=priority,
            rationale=rationale,
            deadline=deadline,
            scope_type="SITE",
            scope_json={"site_id": str(site_id)},
            created_by=actor,
        )
        self.session.add(row)
        self.session.flush()
        self._audit(row, "CREATED", actor, after={"lifecycle": row.lifecycle.value})
        if activate:
            self._audit(row, "ACTIVATED", actor)
        self.session.flush()
        return row

    def transition(
        self,
        objective_id: uuid.UUID,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        lifecycle: ObjectiveLifecycle,
        actor: str,
        reason: Optional[str] = None,
    ) -> StrategicObjective:
        row = self._objective(objective_id, tenant_id, site_id)
        if (
            row.origin
            in {
                ObjectiveOrigin.DETERMINISTIC,
                ObjectiveOrigin.STATISTICAL,
                ObjectiveOrigin.AI_PROPOSED,
            }
            and lifecycle is ObjectiveLifecycle.ACTIVE
            and row.approval_state is not ObjectiveApproval.APPROVED
        ):
            raise ValueError("derived objective requires approval before activation")
        before = row.lifecycle
        row.lifecycle = lifecycle
        self._audit(
            row,
            lifecycle.value,
            actor,
            reason=reason,
            before={"lifecycle": before.value},
            after={"lifecycle": lifecycle.value},
        )
        self.session.flush()
        return row

    def update_goal(
        self,
        objective_id: uuid.UUID,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        actor: str,
        values: dict[str, Any],
        reason: Optional[str] = None,
    ) -> StrategicObjective:
        row = self._objective(objective_id, tenant_id, site_id)
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for key in ("name", "description", "rationale", "priority", "deadline"):
            if key in values and values[key] is not None:
                before[key] = str(getattr(row, key))
                setattr(row, key, values[key])
                after[key] = str(values[key])
        self._audit(row, "UPDATED", actor, reason=reason, before=before, after=after)
        self.session.flush()
        return row

    def approve(
        self,
        objective_id: uuid.UUID,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        actor: str,
        approved: bool,
        reason: Optional[str] = None,
    ) -> StrategicObjective:
        row = self._objective(objective_id, tenant_id, site_id)
        row.approval_state = ObjectiveApproval.APPROVED if approved else ObjectiveApproval.REJECTED
        row.approved_by = actor if approved else None
        row.approved_at = utcnow() if approved else None
        row.lifecycle = ObjectiveLifecycle.ACTIVE if approved else ObjectiveLifecycle.ARCHIVED
        self._audit(row, "APPROVED" if approved else "REJECTED", actor, reason=reason)
        self.session.flush()
        return row

    def add_relationship(
        self,
        *,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        actor: str,
        relationship_type: ObjectiveRelationshipType = ObjectiveRelationshipType.SUPPORTS,
    ) -> ObjectiveRelationship:
        source = self._objective(source_id, tenant_id, site_id)
        self._objective(target_id, tenant_id, site_id)
        if relationship_type in {
            ObjectiveRelationshipType.SUPPORTS,
            ObjectiveRelationshipType.DEPENDS_ON,
        } and self._reachable(target_id, source_id, tenant_id):
            raise ValueError("objective relationship would create a cycle")
        existing = self.session.scalar(
            select(ObjectiveRelationship).where(
                ObjectiveRelationship.source_objective_id == source_id,
                ObjectiveRelationship.target_objective_id == target_id,
                ObjectiveRelationship.relationship_type == relationship_type,
            )
        )
        if existing:
            return existing
        edge = ObjectiveRelationship(
            tenant_id=tenant_id,
            source_objective_id=source_id,
            target_objective_id=target_id,
            relationship_type=relationship_type,
            created_by=actor,
        )
        self.session.add(edge)
        self._audit(
            source,
            "RELATIONSHIP_ADDED",
            actor,
            after={"target_id": str(target_id), "type": relationship_type.value},
        )
        self.session.flush()
        return edge

    def _reachable(self, start: uuid.UUID, destination: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        edges = list(
            self.session.scalars(
                select(ObjectiveRelationship).where(
                    ObjectiveRelationship.tenant_id == tenant_id,
                    ObjectiveRelationship.relationship_type.in_(
                        [ObjectiveRelationshipType.SUPPORTS, ObjectiveRelationshipType.DEPENDS_ON]
                    ),
                )
            )
        )
        graph: dict[uuid.UUID, set[uuid.UUID]] = {}
        for edge in edges:
            graph.setdefault(edge.source_objective_id, set()).add(edge.target_objective_id)
        pending, seen = [start], set()
        while pending:
            current = pending.pop()
            if current == destination:
                return True
            if current not in seen:
                seen.add(current)
                pending.extend(graph.get(current, set()))
        return False

    def create_target(
        self,
        *,
        objective: StrategicObjective,
        metric: MetricDefinition,
        family: TargetFamily,
        direction: TargetDirection,
        target_value: Optional[Decimal],
        actor: str,
        unit: Optional[str] = None,
        condition: Optional[dict[str, Any]] = None,
        origin: ObjectiveOrigin = ObjectiveOrigin.USER_DEFINED,
        approval: ObjectiveApproval = ObjectiveApproval.NOT_REQUIRED,
        suggested_value: Optional[Decimal] = None,
    ) -> ObjectiveTarget:
        target = ObjectiveTarget(
            tenant_id=objective.tenant_id,
            objective_id=objective.id,
            metric_definition_id=metric.id,
            family=family,
            direction=direction,
            unit=unit or metric.unit,
            target_value=target_value,
            condition_json=condition or {},
            entity_scope_json=objective.scope_json,
            measurement_binding_json={
                "metric_key": metric.key,
                "authoritative_source": metric.source_system,
            },
            measurement_health=ObjectiveMeasurementHealth.INSUFFICIENT_DATA
            if metric.currently_measurable
            else ObjectiveMeasurementHealth.NOT_YET_MEASURABLE,
            approval_state=approval,
            origin=origin,
            suggested_value=suggested_value,
        )
        self.session.add(target)
        # A supported binding without a resolved value is not "unmeasurable". Keep the
        # persisted health honest while presentation exposes capability and binding separately.
        objective.measurement_health = (
            ObjectiveMeasurementHealth.INSUFFICIENT_DATA
            if metric.currently_measurable
            else ObjectiveMeasurementHealth.NOT_YET_MEASURABLE
        )
        self._audit(
            objective,
            "TARGET_CREATED",
            actor,
            after={
                "metric_key": metric.key,
                "target_value": str(target_value) if target_value is not None else None,
            },
        )
        self.session.flush()
        return target

    def record_measurement(
        self,
        *,
        target: ObjectiveTarget,
        value: Optional[Decimal],
        period_start: datetime,
        period_end: datetime,
        measured_at: datetime,
        freshness_state: str,
        readiness_state: str,
        method_key: str,
        method_version: str,
        rights_policy_id: Optional[uuid.UUID] = None,
        data_asset_id: Optional[uuid.UUID] = None,
        source_reference: Optional[str] = None,
    ) -> ObjectiveMeasurement:
        identity = stable_hash(
            {
                "target_id": target.id,
                "period_start": period_start,
                "period_end": period_end,
                "value": value,
                "method_key": method_key,
                "method_version": method_version,
                "source_reference": source_reference,
            }
        )
        existing = self.session.scalar(
            select(ObjectiveMeasurement).where(ObjectiveMeasurement.identity_hash == identity)
        )
        if existing:
            return existing
        prior = self.session.scalar(
            select(ObjectiveMeasurement)
            .where(
                ObjectiveMeasurement.target_id == target.id,
                ObjectiveMeasurement.effective_end.is_(None),
            )
            .order_by(ObjectiveMeasurement.measured_at.desc())
        )
        if prior:
            prior.effective_end = measured_at
        row = ObjectiveMeasurement(
            tenant_id=target.tenant_id,
            target_id=target.id,
            value=value,
            unit=target.unit,
            period_start=period_start,
            period_end=period_end,
            measured_at=measured_at,
            data_asset_id=data_asset_id,
            source_reference=source_reference,
            rights_policy_id=rights_policy_id,
            freshness_state=freshness_state,
            readiness_state=readiness_state,
            method_key=method_key,
            method_version=method_version,
            identity_hash=identity,
        )
        self.session.add(row)
        target.current_value = value
        target.current_period_start = period_start
        target.current_period_end = period_end
        target.measurement_health = (
            ObjectiveMeasurementHealth.STALE_DATA
            if freshness_state == "STALE"
            else ObjectiveMeasurementHealth.MEASURABLE
            if value is not None and readiness_state == "READY"
            else ObjectiveMeasurementHealth.INSUFFICIENT_DATA
        )
        self.session.flush()
        return row

    def decompose(
        self, objective_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID, actor: str
    ) -> ObjectiveDerivation:
        metrics = self.ensure_registry()
        parent = self._objective(objective_id, tenant_id, site_id)
        rule = self.session.scalar(
            select(DecompositionRule).where(
                DecompositionRule.key == "REVENUE_TO_REQUIRED_TRAFFIC",
                DecompositionRule.version == "1",
                DecompositionRule.enabled.is_(True),
            )
        )
        if (
            parent.level is not ObjectiveLevel.BUSINESS
            or parent.objective_type is not ObjectiveType.REVENUE
            or rule is None
        ):
            parent.decomposition_state = DecompositionState.BLOCKED_UNSUPPORTED_METRIC
            raise ValueError("no enabled deterministic rule supports this objective")
        plan = self.session.scalar(
            select(DecompositionPlan).where(
                DecompositionPlan.objective_id == parent.id,
                DecompositionPlan.name == "Deterministic plan v1",
                DecompositionPlan.status.notin_(
                    [DecompositionPlanStatus.REJECTED, DecompositionPlanStatus.SUPERSEDED]
                ),
            )
        )
        if plan is None:
            plan = DecompositionPlan(
                tenant_id=tenant_id,
                objective_id=parent.id,
                name="Deterministic plan v1",
                status=DecompositionPlanStatus.AWAITING_APPROVAL,
                origin=ObjectiveOrigin.DETERMINISTIC,
                selected=False,
                provenance_json={"method": "DETERMINISTIC"},
            )
            self.session.add(plan)
            self.session.flush()
        revenue_target = self.session.scalar(
            select(ObjectiveTarget)
            .where(
                ObjectiveTarget.objective_id == parent.id,
                ObjectiveTarget.metric_definition_id == metrics["MONTHLY_REVENUE"].id,
            )
            .order_by(ObjectiveTarget.created_at.desc())
        )
        input_measurement = self.session.scalar(
            select(ObjectiveMeasurement)
            .join(ObjectiveTarget, ObjectiveTarget.id == ObjectiveMeasurement.target_id)
            .where(
                ObjectiveTarget.tenant_id == tenant_id,
                ObjectiveTarget.metric_definition_id == metrics["REVENUE_PER_VISITOR"].id,
                ObjectiveMeasurement.effective_end.is_(None),
            )
            .order_by(ObjectiveMeasurement.measured_at.desc())
        )
        missing = (
            revenue_target is None
            or revenue_target.target_value is None
            or input_measurement is None
            or input_measurement.value is None
        )
        rights_policy = (
            self.session.get(DataRightsPolicy, input_measurement.rights_policy_id)
            if input_measurement and input_measurement.rights_policy_id
            else None
        )
        rights = bool(
            rights_policy
            and rights_policy.deterministic_analysis_allowed is RightsDecision.ALLOWED
            and rights_policy.derived_storage_allowed is RightsDecision.ALLOWED
        )
        stale = bool(input_measurement and input_measurement.freshness_state == "STALE")
        inputs = {
            "monthly_revenue_target": str(revenue_target.target_value)
            if revenue_target and revenue_target.target_value is not None
            else None,
            "revenue_per_qualified_visitor": str(input_measurement.value)
            if input_measurement and input_measurement.value is not None
            else None,
            "measurement_id": str(input_measurement.id) if input_measurement else None,
        }
        blocked_reason: Optional[str] = None
        state = DecompositionState.AWAITING_APPROVAL
        if missing:
            state, blocked_reason = (
                DecompositionState.BLOCKED_MISSING_DATA,
                "Authoritative monthly revenue target and revenue-per-qualified-visitor measurement are required.",
            )
        elif not rights:
            state, blocked_reason = (
                DecompositionState.BLOCKED_RIGHTS,
                "The input measurement has no reviewed rights policy for deterministic analysis.",
            )
        elif stale:
            state, blocked_reason = (
                DecompositionState.BLOCKED_STALE_DATA,
                "The revenue-per-qualified-visitor input is stale; policy forbids recalculation.",
            )
        identity = stable_hash(
            {
                "parent": str(parent.id),
                "rule": "REVENUE_TO_REQUIRED_TRAFFIC",
                "version": "1",
                "inputs": inputs,
                "rights": "ALLOWED" if rights else "UNKNOWN",
                "freshness": input_measurement.freshness_state if input_measurement else "MISSING",
            }
        )
        existing = self.session.scalar(
            select(ObjectiveDerivation).where(ObjectiveDerivation.identity_hash == identity)
        )
        if existing:
            return existing
        parent.decomposition_state = state
        derivation = ObjectiveDerivation(
            tenant_id=tenant_id,
            decomposition_plan_id=plan.id,
            source_objective_id=parent.id,
            rule_id=rule.id,
            rule_key=rule.key,
            rule_version=rule.version,
            formula=rule.formula,
            required_inputs_json=rule.required_metrics_json,
            input_values_json=inputs,
            output_value=None,
            source_references_json=[{"measurement_id": str(input_measurement.id)}]
            if input_measurement
            else [],
            assumptions_json=rule.assumptions_json,
            rights_state="ALLOWED" if rights else "UNKNOWN",
            readiness_state="STALE" if stale else "READY" if not missing else "MISSING",
            result_status=DerivationResultStatus.BLOCKED
            if blocked_reason
            else DerivationResultStatus.CURRENT,
            blocked_reason=blocked_reason,
            identity_hash=identity,
            executed_at=utcnow(),
        )
        self.session.add(derivation)
        if blocked_reason:
            self._audit(
                parent,
                "DECOMPOSITION_BLOCKED",
                actor,
                reason=blocked_reason,
                after={"state": state.value},
            )
            self.session.flush()
            return derivation
        assert revenue_target is not None and revenue_target.target_value is not None
        assert input_measurement is not None and input_measurement.value is not None
        if input_measurement.value <= 0:
            raise ValueError("revenue per qualified visitor must be greater than zero")
        result = (revenue_target.target_value / input_measurement.value).quantize(
            Decimal("1"), rounding=ROUND_CEILING
        )
        child = StrategicObjective(
            tenant_id=tenant_id,
            site_id=site_id,
            name="Reach required qualified visitors",
            description="Deterministically derived from the approved business revenue target and measured revenue per qualified visitor.",
            level=ObjectiveLevel.STRATEGIC_GROWTH,
            objective_type=ObjectiveType.GROWTH,
            lifecycle=ObjectiveLifecycle.PROPOSED,
            origin=ObjectiveOrigin.DETERMINISTIC,
            approval_state=ObjectiveApproval.PENDING,
            progress_state=ObjectiveProgress.UNKNOWN,
            measurement_health=ObjectiveMeasurementHealth.NOT_YET_MEASURABLE,
            decomposition_state=DecompositionState.NOT_STARTED,
            feasibility_state=ObjectiveFeasibility.NOT_ASSESSED,
            priority=parent.priority,
            rationale=f"Supports {parent.name}",
            scope_type="SITE",
            scope_json=parent.scope_json,
            created_by="GIS_DETERMINISTIC",
        )
        self.session.add(child)
        self.session.flush()
        target = self.create_target(
            objective=child,
            metric=metrics["REQUIRED_QUALIFIED_VISITORS"],
            family=TargetFamily.ABSOLUTE_METRIC,
            direction=TargetDirection.AT_LEAST,
            target_value=result,
            actor="GIS_DETERMINISTIC",
            origin=ObjectiveOrigin.DETERMINISTIC,
            approval=ObjectiveApproval.PENDING,
        )
        self.add_relationship(
            tenant_id=tenant_id,
            site_id=site_id,
            source_id=child.id,
            target_id=parent.id,
            actor="GIS_DETERMINISTIC",
        )
        prior = self.session.scalar(
            select(ObjectiveDerivation)
            .where(
                ObjectiveDerivation.source_objective_id == parent.id,
                ObjectiveDerivation.rule_key == rule.key,
                ObjectiveDerivation.result_status == DerivationResultStatus.CURRENT,
                ObjectiveDerivation.id != derivation.id,
            )
            .order_by(ObjectiveDerivation.executed_at.desc())
        )
        if prior:
            prior.result_status = DerivationResultStatus.SUPERSEDED
            derivation.supersedes_derivation_id = prior.id
            if prior.generated_objective_id:
                old = self.session.get(StrategicObjective, prior.generated_objective_id)
                if old:
                    old.lifecycle = ObjectiveLifecycle.ARCHIVED
        derivation.output_value = result
        derivation.generated_objective_id = child.id
        derivation.generated_target_id = target.id
        self._audit(
            parent,
            "DECOMPOSED",
            actor,
            after={"rule": rule.key, "output": str(result), "child_id": str(child.id)},
        )
        self.session.flush()
        return derivation

    def override_target(
        self, target_id: uuid.UUID, tenant_id: uuid.UUID, value: Decimal, actor: str, rationale: str
    ) -> ObjectiveTarget:
        target = self.session.scalar(
            select(ObjectiveTarget)
            .join(StrategicObjective)
            .where(ObjectiveTarget.id == target_id, ObjectiveTarget.tenant_id == tenant_id)
        )
        if target is None:
            raise ValueError("target not found in tenant scope")
        objective = self.session.get(StrategicObjective, target.objective_id)
        assert objective is not None
        original = target.target_value
        target.suggested_value = target.suggested_value or original
        target.target_value = value
        target.origin = ObjectiveOrigin.USER_OVERRIDE
        target.override_rationale = rationale
        target.approval_state = ObjectiveApproval.APPROVED
        self._audit(
            objective,
            "TARGET_OVERRIDDEN",
            actor,
            reason=rationale,
            before={"target_value": str(original)},
            after={"target_value": str(value), "suggested_value": str(target.suggested_value)},
        )
        self.session.flush()
        return target

    @staticmethod
    def progress(target: ObjectiveTarget) -> dict[str, Any]:
        current, desired, baseline = (
            target.current_value,
            target.target_value,
            target.baseline_value,
        )
        gap: Optional[Decimal] = None
        achieved: Optional[bool] = None
        percent: Optional[Decimal] = None
        if current is not None:
            if target.direction is TargetDirection.OUTRANK_ENTITY:
                competitor = target.condition_json.get("competitor_rank")
                if competitor is not None:
                    competitor_rank = Decimal(str(competitor))
                    achieved = current < competitor_rank
                    gap = max(Decimal(0), current - competitor_rank + 1)
            elif desired is None:
                pass
            elif target.direction in {TargetDirection.AT_LEAST, TargetDirection.INCREASE_BY}:
                gap, achieved = max(Decimal(0), desired - current), current >= desired
            elif target.direction in {TargetDirection.AT_MOST, TargetDirection.RANK_AT_OR_ABOVE}:
                gap, achieved = max(Decimal(0), current - desired), current <= desired
            elif (
                target.direction is TargetDirection.BETWEEN
                and target.target_upper_value is not None
            ):
                achieved = desired <= current <= target.target_upper_value
                gap = (
                    desired - current
                    if current < desired
                    else current - target.target_upper_value
                    if current > target.target_upper_value
                    else Decimal(0)
                )
            if (
                target.family not in {TargetFamily.RANK, TargetFamily.COMPETITIVE}
                and baseline is not None
                and desired is not None
                and desired != baseline
            ):
                percent = (current - baseline) / (desired - baseline) * 100
        return {
            "baseline": baseline,
            "current": current,
            "target": desired,
            "gap": gap,
            "achieved": achieved,
            "progress_percent": percent,
            "linear_progress_applicable": target.family
            not in {TargetFamily.RANK, TargetFamily.COMPETITIVE},
            "measurement_health": target.measurement_health.value,
        }
