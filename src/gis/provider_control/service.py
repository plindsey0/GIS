from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from gis.models import (
    DataSource,
    DataSourceConnection,
    IngestionRun,
    ProviderCapability,
    ProviderCapabilityPolicy,
    ProviderCollectionPolicy,
    ProviderCollectionTarget,
    ProviderDefinition,
    ProviderPolicyAuditEvent,
    ProviderPricingConfiguration,
    ProviderUsageEvent,
    ScheduleDefinition,
    Site,
)


@dataclass(frozen=True)
class Preflight:
    provider: str
    capability: str
    target_count: int
    estimated_requests: int
    estimated_units: Decimal
    estimated_cost: Optional[Decimal]
    currency: str
    cost_semantics: str
    can_execute: bool
    blocking_reasons: list[str]
    warnings: list[str]
    reservation_id: Optional[uuid.UUID] = None


class ProviderControlService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def provider(self, key: str) -> ProviderDefinition:
        row = self.session.scalar(
            select(ProviderDefinition).where(ProviderDefinition.provider_key == key)
        )
        if not row:
            raise ValueError("provider not found")
        return row

    def policy(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        provider_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Optional[ProviderCollectionPolicy]:
        query = select(ProviderCollectionPolicy).where(
            ProviderCollectionPolicy.tenant_id == tenant_id,
            ProviderCollectionPolicy.site_id == site_id,
            ProviderCollectionPolicy.provider_id == provider_id,
        )
        return self.session.scalar(query.with_for_update() if lock else query)

    def capability(self, provider_id: uuid.UUID, key: str) -> ProviderCapability:
        row = self.session.scalar(
            select(ProviderCapability).where(
                ProviderCapability.provider_id == provider_id,
                ProviderCapability.capability_key == key,
            )
        )
        if not row:
            raise ValueError("provider capability not found")
        return row

    def _connection(
        self,
        policy: Optional[ProviderCollectionPolicy],
        *,
        tenant_id: Optional[uuid.UUID] = None,
        site_id: Optional[uuid.UUID] = None,
        provider_key: Optional[str] = None,
    ) -> Optional[DataSourceConnection]:
        """Resolve authentication independently from collection authorization.

        Legacy connections predate provider policies, so a missing policy must not
        make an existing connection appear absent. Prefer an explicitly selected
        policy connection, then a site connection, then a tenant-wide connection.
        """
        return (
            self.session.get(DataSourceConnection, policy.data_source_connection_id)
            if policy and policy.data_source_connection_id
            else self._legacy_connection(tenant_id, site_id, provider_key)
        )

    def _legacy_connection(
        self,
        tenant_id: Optional[uuid.UUID],
        site_id: Optional[uuid.UUID],
        provider_key: Optional[str],
    ) -> Optional[DataSourceConnection]:
        if tenant_id is None or site_id is None or provider_key is None:
            return None
        source_keys = (
            ("pagespeed", "crux") if provider_key == "google_pagespeed" else (provider_key,)
        )
        return self.session.scalars(
            select(DataSourceConnection)
            .join(DataSource)
            .where(
                DataSourceConnection.tenant_id == tenant_id,
                or_(
                    DataSourceConnection.site_id == site_id,
                    DataSourceConnection.site_id.is_(None),
                ),
                DataSource.key.in_(source_keys),
            )
            .order_by(
                (DataSourceConnection.site_id == site_id).desc(),
                (DataSourceConnection.status == "ACTIVE").desc(),
                DataSourceConnection.created_at.desc(),
            )
        ).first()

    def state(
        self,
        provider: ProviderDefinition,
        policy: Optional[ProviderCollectionPolicy],
        connection: Optional[DataSourceConnection],
    ) -> tuple[str, Optional[str]]:
        if provider.implementation_status not in {"IMPLEMENTED", "PARTIAL"}:
            return "UNAVAILABLE", "ADAPTER_NOT_IMPLEMENTED"
        if not connection:
            return "NOT_CONNECTED", "CONNECTION_MISSING"
        if connection.status.value != "ACTIVE":
            return "BLOCKED_CONNECTION_ERROR", "CONNECTION_INVALID"
        if not policy or not policy.master_enabled or policy.status == "DISABLED":
            return "CONNECTED_DISABLED", "POLICY_DISABLED"
        if policy.status == "PAUSED":
            return "PAUSED", "POLICY_PAUSED"
        if provider.is_commercial and policy.monthly_hard_budget is None:
            return "BLOCKED_NO_BUDGET", "BUDGET_NOT_CONFIGURED"
        return "ACTIVE", None

    def inventory(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        providers = list(
            self.session.scalars(
                select(ProviderDefinition)
                .where(ProviderDefinition.active.is_(True))
                .order_by(ProviderDefinition.display_name)
            )
        )
        items = [self.detail(tenant_id, site_id, row.provider_key) for row in providers]
        return {
            "items": items,
            "summary": {
                "connected": sum(x["connection_state"] == "CONNECTED" for x in items),
                "enabled": sum(
                    x["collection_state"] in {"ACTIVE", "CONNECTED_ENABLED"} for x in items
                ),
                "paid_enabled": sum(
                    x["is_commercial"] and x["collection_state"] == "ACTIVE" for x in items
                ),
                "spend_month": str(sum(Decimal(x["budget"]["spent_month"]) for x in items)),
                "monthly_hard_budget": str(
                    sum(Decimal(x["budget"]["monthly_hard"] or "0") for x in items)
                ),
                "attention": sum(x["blocking_reason"] is not None for x in items),
            },
        }

    def detail(self, tenant_id: uuid.UUID, site_id: uuid.UUID, key: str) -> dict[str, Any]:
        provider = self.provider(key)
        policy = self.policy(tenant_id, site_id, provider.id)
        connection = self._connection(
            policy, tenant_id=tenant_id, site_id=site_id, provider_key=provider.provider_key
        )
        state, reason = self.state(provider, policy, connection)
        capabilities = list(
            self.session.scalars(
                select(ProviderCapability)
                .where(ProviderCapability.provider_id == provider.id)
                .order_by(ProviderCapability.display_name)
            )
        )
        capability_policies = (
            {
                row.capability_id: row
                for row in self.session.scalars(
                    select(ProviderCapabilityPolicy).where(
                        ProviderCapabilityPolicy.collection_policy_id == policy.id
                    )
                )
            }
            if policy
            else {}
        )
        now = datetime.now(timezone.utc)
        day_start, month_start = self._periods(now, policy.timezone if policy else "UTC")
        spent_day = self._spend(tenant_id, site_id, provider.id, day_start)
        spent_month = self._spend(tenant_id, site_id, provider.id, month_start)
        usages = list(
            self.session.scalars(
                select(ProviderUsageEvent)
                .where(
                    ProviderUsageEvent.tenant_id == tenant_id,
                    ProviderUsageEvent.site_id == site_id,
                    ProviderUsageEvent.provider_id == provider.id,
                )
                .order_by(ProviderUsageEvent.occurred_at.desc())
                .limit(30)
            )
        )
        source_keys = ("pagespeed", "crux") if key == "google_pagespeed" else (key,)
        source = self.session.scalars(
            select(DataSource).where(DataSource.key.in_(source_keys)).order_by(DataSource.key)
        ).first()
        connection_id = policy.data_source_connection_id if policy else None
        schedules = (
            list(
                self.session.scalars(
                    select(ScheduleDefinition).where(
                        ScheduleDefinition.tenant_id == tenant_id,
                        ScheduleDefinition.site_id == site_id,
                        ScheduleDefinition.data_source_connection_id == connection_id,
                    )
                )
            )
            if policy and policy.data_source_connection_id
            else []
        )
        last_run = (
            self.session.scalar(
                select(func.max(IngestionRun.completed_at)).where(
                    IngestionRun.data_source_connection_id == policy.data_source_connection_id,
                    IngestionRun.tenant_id == tenant_id,
                    IngestionRun.site_id == site_id,
                    IngestionRun.status == "SUCCEEDED",
                )
            )
            if policy and policy.data_source_connection_id
            else None
        )
        from gis.provider_control.runtime import readiness

        runtime = readiness(self.session, connection) if key == "dataforseo" else None
        execution_blockers: list[str] = []
        budget_warnings: list[str] = []
        if state == "ACTIVE" and policy:
            from gis.models import PermittedUse, RightsStatus
            from gis.provenance.service import evaluate_connection_use

            if (
                connection
                and evaluate_connection_use(
                    self.session, connection, PermittedUse.NORMALIZED_RETENTION
                ).status
                != RightsStatus.ALLOWED
            ):
                execution_blockers.append("RIGHTS_BLOCKED")
            for cap in capabilities:
                cp = capability_policies.get(cap.id)
                if not cp or not cp.enabled:
                    continue
                target = self.session.scalar(
                    select(ProviderCollectionTarget)
                    .where(
                        ProviderCollectionTarget.capability_policy_id == cp.id,
                        ProviderCollectionTarget.enabled.is_(True),
                    )
                    .limit(1)
                )
                if not target or not target.target_value:
                    execution_blockers.append("No targets authorized for an enabled capability")
                    continue
                preflight = self.preflight(
                    tenant_id,
                    site_id,
                    key,
                    cap.capability_key,
                    [target.target_value],
                    1,
                    Decimal(1),
                )
                execution_blockers.extend(preflight.blocking_reasons)
                budget_warnings.extend(preflight.warnings)
        from gis.provider_control.operations import provider_operations

        operations = provider_operations(
            self.session, connection.id if connection else None, tenant_id, site_id
        )
        health = (
            "UNAVAILABLE"
            if state == "UNAVAILABLE"
            else "PAUSED"
            if state == "PAUSED" or (runtime and runtime.get("execution_held"))
            else "DISABLED"
            if state == "CONNECTED_DISABLED"
            else "ATTENTION_REQUIRED"
            if reason
            or execution_blockers
            or operations["current_incidents"]
            or (runtime and not runtime["runnable"])
            else "HEALTHY"
        )
        # Summary covers the whole business month, independently of the recent-event page.
        usage_totals = self.session.execute(
            select(
                func.coalesce(func.sum(ProviderUsageEvent.request_count), 0),
                func.coalesce(
                    func.sum(ProviderUsageEvent.request_count).filter(
                        ProviderUsageEvent.actual_cost.is_(None)
                    ),
                    0,
                ),
                func.sum(ProviderUsageEvent.actual_cost),
                func.sum(ProviderUsageEvent.reserved_cost).filter(
                    ProviderUsageEvent.status == "RESERVED"
                ),
                func.count(ProviderUsageEvent.id),
            ).where(
                ProviderUsageEvent.tenant_id == tenant_id,
                ProviderUsageEvent.site_id == site_id,
                ProviderUsageEvent.provider_id == provider.id,
                ProviderUsageEvent.occurred_at >= month_start,
            )
        ).one()
        return {
            "operations": operations,
            "execution_blockers": list(dict.fromkeys(execution_blockers)),
            "budget_warnings": list(dict.fromkeys(budget_warnings)),
            "operational_health": health,
            "credential_readiness": runtime,
            "execution_readiness": "RUNNABLE"
            if state == "ACTIVE"
            and not execution_blockers
            and (runtime is None or runtime["runnable"])
            else "BLOCKED",
            "cost_state": "UNKNOWN_UNRECONCILED"
            if usage_totals[1]
            else "KNOWN"
            if usage_totals[4]
            else "NO_USAGE",
            "unknown_cost_requests": usage_totals[1],
            "request_count": usage_totals[0],
            "known_actual_cost_month": str(usage_totals[2])
            if usage_totals[2] is not None
            else None,
            "known_reserved_cost_month": str(usage_totals[3])
            if usage_totals[3] is not None
            else None,
            "id": str(provider.id),
            "key": key,
            "name": provider.display_name,
            "description": provider.description,
            "provider_class": provider.provider_class,
            "pricing_model": provider.pricing_model,
            "implementation_status": provider.implementation_status,
            "is_commercial": provider.is_commercial,
            "connection_state": "CONNECTED" if connection else "NOT_CONNECTED",
            "collection_state": state,
            "blocking_reason": reason
            or (
                "CREDENTIAL_UNAVAILABLE"
                if runtime and not runtime["worker_verified"]
                else "PAID_EXECUTION_HELD"
                if runtime and runtime.get("execution_held")
                else None
            ),
            "policy": self._policy_data(policy),
            "budget": {
                "spent_day": str(spent_day),
                "spent_month": str(spent_month),
                "daily_soft": str(policy.daily_soft_budget)
                if policy and policy.daily_soft_budget is not None
                else None,
                "daily_hard": str(policy.daily_hard_budget)
                if policy and policy.daily_hard_budget is not None
                else None,
                "monthly_soft": str(policy.monthly_soft_budget)
                if policy and policy.monthly_soft_budget is not None
                else None,
                "monthly_hard": str(policy.monthly_hard_budget)
                if policy and policy.monthly_hard_budget is not None
                else None,
                "per_run_hard": str(policy.per_run_hard_budget)
                if policy and policy.per_run_hard_budget is not None
                else None,
            },
            "capabilities": [
                {
                    "id": str(cap.id),
                    "key": cap.capability_key,
                    "name": cap.display_name,
                    "description": cap.description,
                    "enabled": bool(
                        capability_policies.get(cap.id) and capability_policies[cap.id].enabled
                    ),
                    "cadence": capability_policies[cap.id].cadence
                    if cap.id in capability_policies
                    else "MANUAL_ONLY",
                    "supports_manual_run": cap.supports_manual_run,
                    "supports_scheduling": cap.supports_scheduling,
                    "targets": self._targets(capability_policies.get(cap.id)),
                }
                for cap in capabilities
            ],
            "usage": [self._usage_data(x) for x in usages],
            "last_collection": last_run,
            "next_collection": min(
                (x.next_scheduled_at for x in schedules if x.next_scheduled_at), default=None
            ),
            "data_source_id": str(source.id) if source else None,
        }

    def configure(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        key: str,
        values: dict[str, Any],
        actor: str,
        reason: Optional[str],
    ) -> ProviderCollectionPolicy:
        provider = self.provider(key)
        site = self.session.get(Site, site_id)
        if not site or site.tenant_id != tenant_id:
            raise ValueError("Site is outside the requested tenant")
        if provider.implementation_status != "IMPLEMENTED":
            raise ValueError("Provider adapter is not implemented")
        connection_id = values.get("data_source_connection_id")
        if connection_id:
            connection = self.session.get(DataSourceConnection, connection_id)
            source = self.session.get(DataSource, connection.data_source_id) if connection else None
            keys = {"pagespeed", "crux"} if key == "google_pagespeed" else {key}
            if (
                not connection
                or connection.tenant_id != tenant_id
                or connection.site_id not in {None, site_id}
                or not source
                or source.key not in keys
            ):
                raise ValueError("Connection is outside this provider and site scope")
        policy = self.policy(tenant_id, site_id, provider.id, lock=True)
        before = self._policy_data(policy)
        if not policy:
            policy = ProviderCollectionPolicy(
                tenant_id=tenant_id,
                site_id=site_id,
                provider_id=provider.id,
                master_enabled=False,
                status="DISABLED",
                currency="USD",
                allow_unknown_cost=False,
                timezone="UTC",
                created_by=actor,
                updated_by=actor,
            )
            self.session.add(policy)
        for field in (
            "data_source_connection_id",
            "currency",
            "daily_soft_budget",
            "daily_hard_budget",
            "monthly_soft_budget",
            "monthly_hard_budget",
            "per_run_hard_budget",
            "daily_request_limit",
            "monthly_request_limit",
            "per_run_request_limit",
            "allow_unknown_cost",
            "timezone",
        ):
            if field in values:
                setattr(policy, field, values[field])
        policy.updated_by = actor
        self._validate(policy)
        self.session.flush()
        self._audit(policy, "POLICY_UPDATED", actor, reason, before, self._policy_data(policy))
        return policy

    def transition(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        key: str,
        action: str,
        actor: str,
        reason: Optional[str],
    ) -> ProviderCollectionPolicy:
        provider = self.provider(key)
        policy = self.policy(tenant_id, site_id, provider.id, lock=True)
        if not policy:
            raise ValueError("collection policy must be configured first")
        before = self._policy_data(policy)
        if action == "ENABLE":
            if provider.implementation_status != "IMPLEMENTED":
                raise ValueError("provider adapter is not implemented")
            if not self._connection(
                policy,
                tenant_id=tenant_id,
                site_id=site_id,
                provider_key=provider.provider_key,
            ):
                raise ValueError("provider connection is required")
            if provider.is_commercial and policy.monthly_hard_budget is None:
                raise ValueError("commercial provider requires a monthly hard budget")
            policy.master_enabled, policy.status = True, "ACTIVE"
        elif action == "DISABLE":
            policy.master_enabled, policy.status = False, "DISABLED"
        elif action == "PAUSE":
            policy.status = "PAUSED"
        elif action == "RESUME":
            policy.status = "ACTIVE" if policy.master_enabled else "DISABLED"
        else:
            raise ValueError("unsupported provider policy action")
        policy.updated_by = actor
        self._audit(policy, action, actor, reason, before, self._policy_data(policy))
        return policy

    def set_capability(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        provider_key: str,
        capability_key: str,
        enabled: bool,
        cadence: str,
        actor: str,
    ) -> ProviderCapabilityPolicy:
        provider = self.provider(provider_key)
        policy = self.policy(tenant_id, site_id, provider.id, lock=True)
        if not policy:
            raise ValueError("collection policy must be configured first")
        cap = self.capability(provider.id, capability_key)
        row = self.session.scalar(
            select(ProviderCapabilityPolicy).where(
                ProviderCapabilityPolicy.collection_policy_id == policy.id,
                ProviderCapabilityPolicy.capability_id == cap.id,
            )
        )
        if not row:
            row = ProviderCapabilityPolicy(collection_policy_id=policy.id, capability_id=cap.id)
            self.session.add(row)
        row.enabled, row.cadence = enabled, cadence
        self.session.flush()
        self._audit(
            policy,
            "CAPABILITY_UPDATED",
            actor,
            None,
            {},
            {"capability": capability_key, "enabled": enabled, "cadence": cadence},
        )
        return row

    def add_target(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        provider_key: str,
        capability_key: str,
        target_type: str,
        target_value: str,
        priority: str,
        actor: str,
    ) -> ProviderCollectionTarget:
        provider = self.provider(provider_key)
        policy = self.policy(tenant_id, site_id, provider.id, lock=True)
        if not policy:
            raise ValueError("collection policy must be configured first")
        capability = self.capability(provider.id, capability_key)
        capability_policy = self.session.scalar(
            select(ProviderCapabilityPolicy).where(
                ProviderCapabilityPolicy.collection_policy_id == policy.id,
                ProviderCapabilityPolicy.capability_id == capability.id,
            )
        )
        if not capability_policy:
            raise ValueError("capability policy must be configured first")
        target = self.session.scalar(
            select(ProviderCollectionTarget).where(
                ProviderCollectionTarget.capability_policy_id == capability_policy.id,
                ProviderCollectionTarget.target_type == target_type,
                ProviderCollectionTarget.target_value == target_value,
            )
        )
        if not target:
            target = ProviderCollectionTarget(
                capability_policy_id=capability_policy.id,
                target_type=target_type,
                target_value=target_value,
            )
            self.session.add(target)
        target.enabled = True
        target.priority = priority
        self.session.flush()
        self._audit(
            policy,
            "TARGET_AUTHORIZED",
            actor,
            None,
            {},
            {"capability": capability_key, "type": target_type, "value": target_value},
        )
        return target

    def set_target_enabled(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        provider_key: str,
        target_id: uuid.UUID,
        enabled: bool,
        actor: str,
    ) -> ProviderCollectionTarget:
        provider = self.provider(provider_key)
        policy = self.policy(tenant_id, site_id, provider.id, lock=True)
        if not policy:
            raise ValueError("collection policy must be configured first")
        target = self.session.scalar(
            select(ProviderCollectionTarget)
            .join(ProviderCapabilityPolicy)
            .where(
                ProviderCollectionTarget.id == target_id,
                ProviderCapabilityPolicy.collection_policy_id == policy.id,
            )
        )
        if not target:
            raise ValueError("collection target not found")
        target.enabled = enabled
        self._audit(
            policy,
            "TARGET_ENABLED" if enabled else "TARGET_DISABLED",
            actor,
            None,
            {"target_id": str(target.id), "enabled": not enabled},
            {"target_id": str(target.id), "enabled": enabled},
        )
        return target

    def preflight(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        provider_key: str,
        capability_key: str,
        target_values: list[str],
        estimated_requests: int,
        estimated_units: Decimal,
        reserve: bool = False,
        estimated_cost_override: Optional[Decimal] = None,
    ) -> Preflight:
        provider = self.provider(provider_key)
        policy = self.policy(tenant_id, site_id, provider.id, lock=reserve)
        if not target_values or estimated_requests < 1 or estimated_units <= 0:
            raise ValueError("Preflight requires targets and positive request/unit estimates")
        cap = self.capability(provider.id, capability_key)
        reasons: list[str] = []
        warnings: list[str] = []
        connection = self._connection(
            policy, tenant_id=tenant_id, site_id=site_id, provider_key=provider.provider_key
        )
        state, reason = self.state(provider, policy, connection)
        if reason:
            reasons.append(reason)
        cap_policy = (
            self.session.scalar(
                select(ProviderCapabilityPolicy).where(
                    ProviderCapabilityPolicy.collection_policy_id == policy.id,
                    ProviderCapabilityPolicy.capability_id == cap.id,
                )
            )
            if policy
            else None
        )
        if not cap_policy or not cap_policy.enabled:
            reasons.append("CAPABILITY_DISABLED")
        authorized = (
            {
                x.target_value
                for x in self.session.scalars(
                    select(ProviderCollectionTarget).where(
                        ProviderCollectionTarget.capability_policy_id == cap_policy.id,
                        ProviderCollectionTarget.enabled.is_(True),
                    )
                )
            }
            if cap_policy
            else set()
        )
        if target_values and not set(target_values).issubset(authorized):
            reasons.append("TARGET_NOT_AUTHORIZED")
        pricing = self._pricing(provider.id, cap.id, tenant_id, site_id)
        # Caller estimates are not authoritative pricing and cannot undercut policy.
        cost = None
        semantics = "UNKNOWN"
        if cost is None and pricing and pricing.unit_price is not None and pricing.units_per_price:
            cost = (estimated_units / pricing.units_per_price) * pricing.unit_price
            semantics = "GIS_ESTIMATED"
        if pricing and policy and pricing.currency != policy.currency:
            reasons.append("PRICING_CURRENCY_MISMATCH")
        if (
            provider.is_commercial
            and cost is None
            and not (
                policy
                and policy.allow_unknown_cost
                and policy.per_run_request_limit
                and policy.daily_request_limit
                and policy.monthly_request_limit
            )
        ):
            reasons.append("PROJECTED_COST_UNKNOWN")
        if policy:
            self._budget_reasons(policy, estimated_requests, cost, reasons, warnings)
        result = Preflight(
            provider_key,
            capability_key,
            len(target_values),
            estimated_requests,
            estimated_units,
            cost,
            policy.currency if policy else "USD",
            semantics,
            not reasons,
            list(dict.fromkeys(reasons)),
            warnings,
        )
        if reserve and result.can_execute:
            assert policy is not None
            event = ProviderUsageEvent(
                tenant_id=tenant_id,
                site_id=site_id,
                provider_id=provider.id,
                capability_id=cap.id,
                collection_policy_id=policy.id,
                data_source_connection_id=policy.data_source_connection_id,
                occurred_at=datetime.now(timezone.utc),
                request_count=estimated_requests,
                unit_count=estimated_units,
                unit_type=cap.unit_type,
                estimated_cost=cost,
                reserved_cost=cost or Decimal("0"),
                currency=result.currency,
                cost_semantics=semantics,
                status="RESERVED",
                metadata_json={"targets": target_values},
            )
            self.session.add(event)
            self.session.flush()
            result = Preflight(**{**asdict(result), "reservation_id": event.id})
        return result

    def reconcile(
        self,
        reservation_id: uuid.UUID,
        *,
        actual_cost: Optional[Decimal],
        semantics: str,
        status: str,
        ingestion_run_id: Optional[uuid.UUID] = None,
    ) -> ProviderUsageEvent:
        row = self.session.scalar(
            select(ProviderUsageEvent)
            .where(ProviderUsageEvent.id == reservation_id)
            .with_for_update()
        )
        if not row or row.status != "RESERVED":
            raise ValueError("active reservation not found")
        row.actual_cost, row.cost_semantics, row.status, row.ingestion_run_id, row.reserved_cost = (
            actual_cost,
            semantics,
            status,
            ingestion_run_id,
            Decimal("0"),
        )
        return row

    def _budget_reasons(
        self,
        p: ProviderCollectionPolicy,
        requests: int,
        cost: Optional[Decimal],
        reasons: list[str],
        warnings: list[str],
    ) -> None:
        now = datetime.now(timezone.utc)
        day, month = self._periods(now, p.timezone)
        day_spend = self._spend(p.tenant_id, p.site_id, p.provider_id, day)
        month_spend = self._spend(p.tenant_id, p.site_id, p.provider_id, month)
        day_requests = self._requests(p.tenant_id, p.site_id, p.provider_id, day)
        month_requests = self._requests(p.tenant_id, p.site_id, p.provider_id, month)
        if p.per_run_request_limit is not None and requests > p.per_run_request_limit:
            reasons.append("PER_RUN_REQUEST_LIMIT_EXCEEDED")
        if p.daily_request_limit is not None and day_requests + requests > p.daily_request_limit:
            reasons.append("DAILY_REQUEST_LIMIT_EXCEEDED")
        if (
            p.monthly_request_limit is not None
            and month_requests + requests > p.monthly_request_limit
        ):
            reasons.append("MONTHLY_REQUEST_LIMIT_EXCEEDED")
        if cost is not None:
            if p.per_run_hard_budget is not None and cost > p.per_run_hard_budget:
                reasons.append("PER_RUN_BUDGET_EXCEEDED")
            if p.daily_hard_budget is not None and day_spend + cost > p.daily_hard_budget:
                reasons.append("DAILY_BUDGET_EXHAUSTED")
            if p.monthly_hard_budget is not None and month_spend + cost > p.monthly_hard_budget:
                reasons.append("MONTHLY_BUDGET_EXHAUSTED")
            if p.daily_soft_budget is not None and day_spend + cost > p.daily_soft_budget:
                warnings.append("DAILY_SOFT_BUDGET_EXCEEDED")
            if p.monthly_soft_budget is not None and month_spend + cost > p.monthly_soft_budget:
                warnings.append("MONTHLY_SOFT_BUDGET_EXCEEDED")

    def _requests(
        self,
        tenant_id: uuid.UUID,
        site_id: Optional[uuid.UUID],
        provider_id: uuid.UUID,
        start: datetime,
    ) -> int:
        return int(
            self.session.scalar(
                select(func.coalesce(func.sum(ProviderUsageEvent.request_count), 0)).where(
                    ProviderUsageEvent.tenant_id == tenant_id,
                    ProviderUsageEvent.site_id == site_id,
                    ProviderUsageEvent.provider_id == provider_id,
                    ProviderUsageEvent.occurred_at >= start,
                )
            )
            or 0
        )

    def _pricing(
        self,
        provider_id: uuid.UUID,
        capability_id: Optional[uuid.UUID] = None,
        tenant_id: Optional[uuid.UUID] = None,
        site_id: Optional[uuid.UUID] = None,
    ) -> Optional[ProviderPricingConfiguration]:
        now = datetime.now(timezone.utc)
        return self.session.scalar(
            select(ProviderPricingConfiguration)
            .where(
                ProviderPricingConfiguration.provider_id == provider_id,
                or_(
                    (ProviderPricingConfiguration.tenant_id == tenant_id)
                    & (ProviderPricingConfiguration.site_id == site_id),
                    ProviderPricingConfiguration.tenant_id.is_(None)
                    & ProviderPricingConfiguration.site_id.is_(None),
                ),
                or_(
                    ProviderPricingConfiguration.capability_id == capability_id,
                    ProviderPricingConfiguration.capability_id.is_(None),
                ),
                ProviderPricingConfiguration.effective_start_at <= now,
                or_(
                    ProviderPricingConfiguration.effective_end_at.is_(None),
                    ProviderPricingConfiguration.effective_end_at > now,
                ),
            )
            .order_by(
                ProviderPricingConfiguration.tenant_id.desc().nullslast(),
                ProviderPricingConfiguration.capability_id.desc().nullslast(),
                ProviderPricingConfiguration.effective_start_at.desc(),
            )
            .limit(1)
        )

    def _spend(
        self,
        tenant_id: uuid.UUID,
        site_id: Optional[uuid.UUID],
        provider_id: uuid.UUID,
        start: datetime,
    ) -> Decimal:
        actual = func.coalesce(
            ProviderUsageEvent.actual_cost,
            ProviderUsageEvent.estimated_cost,
            ProviderUsageEvent.reserved_cost,
            0,
        )
        return Decimal(
            self.session.scalar(
                select(func.coalesce(func.sum(actual), 0)).where(
                    ProviderUsageEvent.tenant_id == tenant_id,
                    ProviderUsageEvent.site_id == site_id,
                    ProviderUsageEvent.provider_id == provider_id,
                    ProviderUsageEvent.occurred_at >= start,
                )
            )
            or 0
        )

    @staticmethod
    def _periods(now: datetime, timezone_name: str) -> tuple[datetime, datetime]:
        local = now.astimezone(ZoneInfo(timezone_name))
        day = local.replace(hour=0, minute=0, second=0, microsecond=0)
        month = day.replace(day=1)
        return day.astimezone(timezone.utc), month.astimezone(timezone.utc)

    @staticmethod
    def _validate(p: ProviderCollectionPolicy) -> None:
        for soft, hard in (
            (p.daily_soft_budget, p.daily_hard_budget),
            (p.monthly_soft_budget, p.monthly_hard_budget),
        ):
            if soft is not None and hard is not None and soft > hard:
                raise ValueError("soft budget cannot exceed hard budget")
        ZoneInfo(p.timezone)

    @staticmethod
    def _policy_data(p: Optional[ProviderCollectionPolicy]) -> Optional[dict[str, Any]]:
        if not p:
            return None
        return {
            "id": str(p.id),
            "master_enabled": p.master_enabled,
            "status": p.status,
            "currency": p.currency,
            "connection_id": str(p.data_source_connection_id)
            if p.data_source_connection_id
            else None,
            "allow_unknown_cost": p.allow_unknown_cost,
        }

    def _targets(self, cp: Optional[ProviderCapabilityPolicy]) -> list[dict[str, Any]]:
        if not cp:
            return []
        return [
            {
                "id": str(x.id),
                "type": x.target_type,
                "value": x.target_value,
                "priority": x.priority,
                "enabled": x.enabled,
            }
            for x in self.session.scalars(
                select(ProviderCollectionTarget).where(
                    ProviderCollectionTarget.capability_policy_id == cp.id
                )
            )
        ]

    @staticmethod
    def _usage_data(x: ProviderUsageEvent) -> dict[str, Any]:
        return {
            "id": str(x.id),
            "occurred_at": x.occurred_at,
            "requests": x.request_count,
            "units": str(x.unit_count),
            "estimated_cost": str(x.estimated_cost) if x.estimated_cost is not None else None,
            "actual_cost": str(x.actual_cost) if x.actual_cost is not None else None,
            "cost_semantics": x.cost_semantics,
            "currency": x.currency,
            "status": x.status,
        }

    def _audit(
        self,
        p: ProviderCollectionPolicy,
        action: str,
        actor: str,
        reason: Optional[str],
        before: Any,
        after: Any,
    ) -> None:
        self.session.add(
            ProviderPolicyAuditEvent(
                tenant_id=p.tenant_id,
                site_id=p.site_id,
                provider_id=p.provider_id,
                collection_policy_id=p.id,
                action=action,
                actor=actor,
                reason=reason,
                before_json=before or {},
                after_json=after or {},
                occurred_at=datetime.now(timezone.utc),
            )
        )
