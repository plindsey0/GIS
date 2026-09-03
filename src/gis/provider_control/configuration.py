"""Operator configuration and deterministic projections over the canonical policies."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from gis.api.schemas import ProviderPolicyInput
from gis.models import (
    CollectionTarget,
    CollectionTargetStatus,
    CollectionTargetType,
    DataSource,
    DataSourceConnection,
    Domain,
    OrchestrationRun,
    PipelineDefinition,
    ProviderCapabilityPolicy,
    ProviderCollectionTarget,
    ProviderPolicyAuditEvent,
    ProviderPricingConfiguration,
    ScheduleDefinition,
    Site,
    TrackedQuery,
)
from gis.provider_control.service import ProviderControlService

# Adapter metadata, not an independent execution configuration.
BINDINGS = {
    "SEARCH_PERFORMANCE": ("gsc", "SITE"),
    "BEHAVIORAL_ANALYTICS": ("ga4", "SITE"),
    "LAB_PERFORMANCE": ("experience", "URL"),
    "FIELD_CRUX": ("experience", "URL"),
    "SERP_COLLECTION": ("serp", "QUERY"),
    "DOMAIN_SEARCH_INTELLIGENCE": ("external_search", "DOMAIN"),
}


class CapabilityConfiguration(BaseModel):
    key: str
    enabled: bool = False
    target_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    cadence: str = Field(default="MANUAL_ONLY", pattern="^(MANUAL_ONLY|DAILY|WEEKLY|MONTHLY)$")
    hour: int = Field(default=8, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int = Field(default=1, ge=0, le=6)
    month_day: int = Field(default=1, ge=1, le=28)
    freshness_hours: int = Field(default=168, ge=1, le=8760)
    per_run_limit: int = Field(default=100, ge=1, le=100)
    unit_price: Optional[Decimal] = Field(default=None, ge=0, max_digits=20, decimal_places=8)
    pricing_notes: str = Field(default="", max_length=2000)


class CollectionConfiguration(BaseModel):
    policy: ProviderPolicyInput
    capabilities: list[CapabilityConfiguration] = Field(max_length=20)
    activate: bool = False


def cron(cap: CapabilityConfiguration) -> str:
    day = str(cap.month_day) if cap.cadence == "MONTHLY" else "*"
    weekday = str(cap.weekday) if cap.cadence == "WEEKLY" else "*"
    return f"{cap.minute} {cap.hour} {day} * {weekday}"


class ConfigurationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.control = ProviderControlService(session)

    def site(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> Site:
        row = self.session.scalar(
            select(Site).where(Site.id == site_id, Site.tenant_id == tenant_id)
        )
        if not row:
            raise ValueError("Site is outside the requested tenant.")
        return row

    def choices(self, tenant_id: uuid.UUID, site_id: uuid.UUID, kind: str) -> list[dict[str, str]]:
        site = self.site(tenant_id, site_id)
        extra = (
            [
                {
                    "id": str(t.id),
                    "label": t.display_value,
                    "value": t.normalized_identity,
                    "type": kind,
                }
                for t in self.session.scalars(
                    select(CollectionTarget).where(
                        CollectionTarget.tenant_id == tenant_id,
                        CollectionTarget.site_id == site_id,
                        CollectionTarget.target_type == CollectionTargetType(kind),
                        CollectionTarget.status == CollectionTargetStatus.ACTIVE,
                    )
                )
            ]
            if kind in {"URL", "DOMAIN"}
            else []
        )
        if kind in {"SITE", "URL"}:
            return extra + [
                {
                    "id": str(site.id),
                    "label": site.name if kind == "SITE" else site.canonical_url,
                    "value": str(site.id) if kind == "SITE" else site.canonical_url,
                    "type": kind,
                }
            ]
        rows: list[Any] = (
            list(
                self.session.scalars(
                    select(TrackedQuery).where(
                        TrackedQuery.tenant_id == tenant_id, TrackedQuery.site_id == site_id
                    )
                )
            )
            if kind == "QUERY"
            else list(
                self.session.scalars(
                    select(Domain).where(Domain.tenant_id == tenant_id, Domain.site_id == site_id)
                )
            )
        )
        return extra + [
            {
                "id": str(row.id),
                "label": row.query_text if isinstance(row, TrackedQuery) else row.hostname,
                "value": row.normalized_query if isinstance(row, TrackedQuery) else row.hostname,
                "type": kind,
            }
            for row in rows
            if not isinstance(row, TrackedQuery) or row.active
        ]

    def read(self, tenant_id: uuid.UUID, site_id: uuid.UUID, key: str) -> dict[str, Any]:
        site = self.site(tenant_id, site_id)
        detail = self.control.detail(tenant_id, site_id, key)
        provider = self.control.provider(key)
        policy = self.control.policy(tenant_id, site_id, provider.id)
        source_keys = ["pagespeed", "crux"] if key == "google_pagespeed" else [key]
        connections = self.session.scalars(
            select(DataSourceConnection)
            .join(DataSource)
            .where(
                DataSourceConnection.tenant_id == tenant_id,
                or_(
                    DataSourceConnection.site_id == site_id, DataSourceConnection.site_id.is_(None)
                ),
                DataSource.key.in_(source_keys),
            )
            .order_by(DataSourceConnection.created_at)
        ).all()
        capabilities = []
        for cap in detail["capabilities"]:
            binding = BINDINGS.get(cap["key"])
            if not binding:
                continue
            cp = (
                self.session.scalar(
                    select(ProviderCapabilityPolicy).where(
                        ProviderCapabilityPolicy.collection_policy_id == policy.id,
                        ProviderCapabilityPolicy.capability_id == uuid.UUID(cap["id"]),
                    )
                )
                if policy
                else None
            )
            price = self.control._pricing(provider.id, uuid.UUID(cap["id"]), tenant_id, site_id)
            targets = (
                self.session.scalars(
                    select(ProviderCollectionTarget).where(
                        ProviderCollectionTarget.capability_policy_id == cp.id,
                        ProviderCollectionTarget.enabled.is_(True),
                    )
                ).all()
                if cp
                else []
            )
            schedule_spec = dict(cp.schedule_configuration_json) if cp else {}
            legacy_cron = None
            if cp and not schedule_spec:
                legacy = self.session.scalar(
                    select(ScheduleDefinition)
                    .join(PipelineDefinition)
                    .where(
                        ScheduleDefinition.tenant_id == tenant_id,
                        ScheduleDefinition.site_id == site_id,
                        PipelineDefinition.key == binding[0],
                    )
                    .order_by(ScheduleDefinition.created_at)
                    .limit(1)
                )
                if legacy:
                    legacy_cron = legacy.cron_expression
                    parts = legacy.cron_expression.split()
                    if len(parts) == 5 and parts[0].isdigit() and parts[1].isdigit():
                        schedule_spec = {
                            "minute": int(parts[0]),
                            "hour": int(parts[1]),
                            "weekday": int(parts[4]) if parts[4].isdigit() else 1,
                            "month_day": int(parts[2]) if parts[2].isdigit() else 1,
                        }
            capabilities.append(
                {
                    **cap,
                    "target_type": binding[1],
                    "choices": self.choices(tenant_id, site_id, binding[1]),
                    "target_ids": [
                        str(t.target_reference_id) for t in targets if t.target_reference_id
                    ],
                    "hour": schedule_spec.get("hour", 8),
                    "minute": schedule_spec.get("minute", 0),
                    "weekday": schedule_spec.get("weekday", 1),
                    "month_day": schedule_spec.get("month_day", 1),
                    "legacy_cron": legacy_cron,
                    "freshness_hours": (cp.freshness_target_seconds or 604800) // 3600
                    if cp
                    else 168,
                    "per_run_limit": cp.per_run_limit or 100 if cp else 100,
                    "unit_price": str(price.unit_price)
                    if price and price.unit_price is not None
                    else None,
                    "pricing_notes": price.notes or "" if price else "",
                    "pricing_provenance": price.provenance if price else "UNKNOWN",
                    "last_verified": price.last_verified_at if price else None,
                }
            )
        fields = ProviderPolicyInput.model_fields.keys() - {"actor", "reason"}
        policy_data = (
            {field: getattr(policy, field) for field in fields}
            if policy
            else {
                "data_source_connection_id": connections[0].id if len(connections) == 1 else None,
                "timezone": site.timezone,
                "currency": "USD",
                "allow_unknown_cost": False,
            }
        )
        history = self.session.scalars(
            select(ProviderPolicyAuditEvent)
            .where(
                ProviderPolicyAuditEvent.tenant_id == tenant_id,
                ProviderPolicyAuditEvent.site_id == site_id,
                ProviderPolicyAuditEvent.provider_id == provider.id,
            )
            .order_by(ProviderPolicyAuditEvent.occurred_at.desc())
            .limit(20)
        ).all()
        recent_runs = (
            self.session.scalars(
                select(OrchestrationRun)
                .where(
                    OrchestrationRun.tenant_id == tenant_id,
                    OrchestrationRun.site_id == site_id,
                    OrchestrationRun.data_source_connection_id == policy.data_source_connection_id,
                )
                .order_by(OrchestrationRun.requested_at.desc())
                .limit(10)
            ).all()
            if policy and policy.data_source_connection_id
            else []
        )
        return {
            "recent_runs": [
                {"id": str(r.id), "status": r.status.value, "at": r.requested_at}
                for r in recent_runs
            ],
            "detail": detail,
            "policy": policy_data,
            "capabilities": capabilities,
            "connections": [
                {
                    "id": str(c.id),
                    "label": c.external_account_id or f"{detail['name']} connection {i + 1}",
                    "status": c.status.value,
                }
                for i, c in enumerate(connections)
            ],
            "history": [
                {"action": h.action, "actor": h.actor, "at": h.occurred_at, "reason": h.reason}
                for h in history
            ],
        }

    def preview(
        self, tenant_id: uuid.UUID, site_id: uuid.UUID, key: str, config: CollectionConfiguration
    ) -> dict[str, Any]:
        self.site(tenant_id, site_id)
        provider = self.control.provider(key)
        blockers: list[str] = []
        try:
            ZoneInfo(config.policy.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Choose a valid IANA timezone.") from exc
        if provider.implementation_status != "IMPLEMENTED":
            blockers.append("The provider adapter is not implemented.")
        connection = (
            self.session.get(DataSourceConnection, config.policy.data_source_connection_id)
            if config.policy.data_source_connection_id
            else None
        )
        source = self.session.get(DataSource, connection.data_source_id) if connection else None
        valid_keys = {"pagespeed", "crux"} if key == "google_pagespeed" else {key}
        if (
            not connection
            or connection.tenant_id != tenant_id
            or connection.site_id not in {None, site_id}
            or not source
            or source.key not in valid_keys
        ):
            blockers.append("Select an existing connection for this provider and site.")
        elif connection.status.value != "ACTIVE":
            blockers.append("The selected connection is not active.")
        if config.policy.currency != "USD":
            blockers.append("This configuration workflow currently supports USD pricing only.")
        if len({c.key for c in config.capabilities}) != len(config.capabilities):
            raise ValueError("Each capability must appear once.")
        if not any(c.enabled for c in config.capabilities):
            blockers.append("Enable at least one supported capability.")
        plans: list[dict[str, Any]] = []
        for cap in config.capabilities:
            self.control.capability(provider.id, cap.key)
            if cap.key not in BINDINGS:
                raise ValueError("Capability has no executable adapter binding.")
            choices = {
                uuid.UUID(c["id"]): c
                for c in self.choices(tenant_id, site_id, BINDINGS[cap.key][1])
            }
            if not set(cap.target_ids).issubset(choices):
                raise ValueError("A selected target is outside the canonical site scope.")
            if len(cap.target_ids) != len(set(cap.target_ids)):
                raise ValueError("Duplicate targets are not allowed.")
            if not cap.enabled:
                continue
            count = len(cap.target_ids)
            if not count:
                blockers.append(
                    f"Select authorized targets for {cap.key.replace('_', ' ').lower()}."
                )
            if count > cap.per_run_limit:
                blockers.append("The target count exceeds the capability collection ceiling.")
            frequency = {
                "MANUAL_ONLY": Decimal(0),
                "DAILY": Decimal(30),
                "WEEKLY": Decimal("4.345"),
                "MONTHLY": Decimal(1),
            }[cap.cadence]
            requests = Decimal(count) * frequency
            cost = (
                requests * cap.unit_price
                if cap.unit_price is not None
                else (None if provider.is_commercial else Decimal(0))
            )
            if (
                provider.is_commercial
                and cap.unit_price is None
                and not (
                    config.policy.allow_unknown_cost
                    and config.policy.per_run_request_limit
                    and config.policy.daily_request_limit
                    and config.policy.monthly_request_limit
                )
            ):
                blockers.append(
                    "Configure pricing, or explicitly permit unknown cost with bounded daily, monthly and per-run request limits."
                )
            if provider.is_commercial and cap.unit_price is not None:
                if (
                    config.policy.per_run_hard_budget is not None
                    and cap.unit_price > config.policy.per_run_hard_budget
                ):
                    blockers.append("One target collection exceeds the per-run hard budget.")
            plans.append(
                {
                    "key": cap.key,
                    "targets": count,
                    "cadence": cap.cadence,
                    "cron": cron(cap),
                    "estimated_requests_month": str(requests),
                    "estimated_cost_month": str(cost) if cost is not None else None,
                }
            )
        if provider.is_commercial:
            if config.policy.monthly_hard_budget is None:
                blockers.append("A commercial provider requires a monthly hard budget.")
            if config.policy.per_run_hard_budget is None:
                blockers.append("A commercial provider requires a per-run hard budget.")
        for soft, hard in (
            (config.policy.daily_soft_budget, config.policy.daily_hard_budget),
            (config.policy.monthly_soft_budget, config.policy.monthly_hard_budget),
        ):
            if soft is not None and hard is not None and soft > hard:
                raise ValueError("Soft budgets cannot exceed hard budgets.")
        # PageSpeed returns LAB and available FIELD in one request; one shared schedule.
        if key == "google_pagespeed" and len([c for c in config.capabilities if c.enabled]) == 2:
            a, b = [c for c in config.capabilities if c.enabled]
            if (a.cadence, cron(a), set(a.target_ids)) != (b.cadence, cron(b), set(b.target_ids)):
                blockers.append(
                    "PageSpeed LAB and FIELD share one retrieval; choose the same targets and schedule."
                )
            plans = plans[:1]
        return {
            "plans": plans,
            "blockers": list(dict.fromkeys(blockers)),
            "can_activate": not blockers,
            "estimated_requests_month": str(
                sum(Decimal(p["estimated_requests_month"]) for p in plans)
            ),
            "estimated_cost_month": None
            if any(p["estimated_cost_month"] is None for p in plans)
            else str(sum(Decimal(p["estimated_cost_month"]) for p in plans)),
            "timezone": config.policy.timezone,
            "paid_calls_made": 0,
            "semantics": "ESTIMATED; one orchestration execution per target; 30 days / 4.345 weeks per month",
        }

    def save(
        self, tenant_id: uuid.UUID, site_id: uuid.UUID, key: str, config: CollectionConfiguration
    ) -> dict[str, Any]:
        preview = self.preview(tenant_id, site_id, key, config)
        provider = self.control.provider(key)
        if provider.implementation_status != "IMPLEMENTED":
            raise ValueError("Planned integrations cannot be configured for execution.")
        if config.activate and preview["blockers"]:
            raise ValueError(" ".join(preview["blockers"]))
        # Validate connection ownership even when saving disabled.
        if config.policy.data_source_connection_id and any(
            "connection" in b.lower() for b in preview["blockers"]
        ):
            raise ValueError("Select an active provider connection in this site scope.")
        policy = self.control.configure(
            tenant_id,
            site_id,
            key,
            config.policy.model_dump(exclude={"actor", "reason"}),
            config.policy.actor,
            config.policy.reason,
        )
        self.control.transition(
            tenant_id, site_id, key, "DISABLE", config.policy.actor, "Configuration replacement"
        )
        old_cps = self.session.scalars(
            select(ProviderCapabilityPolicy).where(
                ProviderCapabilityPolicy.collection_policy_id == policy.id
            )
        ).all()
        for cp in old_cps:
            cp.enabled = False
        for cap in config.capabilities:
            cp = self.control.set_capability(
                tenant_id, site_id, key, cap.key, cap.enabled, cap.cadence, config.policy.actor
            )
            cp.schedule_configuration_json = {
                "hour": cap.hour,
                "minute": cap.minute,
                "weekday": cap.weekday,
                "month_day": cap.month_day,
            }
            cp.freshness_target_seconds, cp.per_run_limit = (
                cap.freshness_hours * 3600,
                cap.per_run_limit,
            )
            choices = {
                uuid.UUID(c["id"]): c
                for c in self.choices(tenant_id, site_id, BINDINGS[cap.key][1])
            }
            targets = self.session.scalars(
                select(ProviderCollectionTarget).where(
                    ProviderCollectionTarget.capability_policy_id == cp.id
                )
            ).all()
            for previous_target in targets:
                previous_target.enabled = False
            for target_id in cap.target_ids:
                target = next((t for t in targets if t.target_reference_id == target_id), None)
                if target is None:
                    target = ProviderCollectionTarget(
                        capability_policy_id=cp.id,
                        target_reference_id=target_id,
                        target_type=BINDINGS[cap.key][1],
                        target_value=choices[target_id]["value"],
                    )
                    self.session.add(target)
                target.enabled = True
            if provider.is_commercial:
                now = datetime.now(timezone.utc)
                previous = self.session.scalars(
                    select(ProviderPricingConfiguration).where(
                        ProviderPricingConfiguration.tenant_id == tenant_id,
                        ProviderPricingConfiguration.site_id == site_id,
                        ProviderPricingConfiguration.capability_id == cp.capability_id,
                        ProviderPricingConfiguration.effective_end_at.is_(None),
                    )
                ).all()
                for price in previous:
                    price.effective_end_at = now
                self.session.add(
                    ProviderPricingConfiguration(
                        tenant_id=tenant_id,
                        site_id=site_id,
                        provider_id=provider.id,
                        capability_id=cp.capability_id,
                        pricing_model="PER_REQUEST",
                        unit_price=cap.unit_price,
                        units_per_price=Decimal(1),
                        currency=config.policy.currency,
                        provenance="USER_CONFIGURED",
                        effective_start_at=now,
                        last_verified_at=now if cap.unit_price is not None else None,
                        notes=cap.pricing_notes,
                    )
                )
        self.session.flush()
        if config.activate:
            self.control.transition(
                tenant_id,
                site_id,
                key,
                "ENABLE",
                config.policy.actor,
                "Explicit reviewed activation",
            )
        self.control._audit(
            policy,
            "CONFIGURATION_SAVED",
            config.policy.actor,
            config.policy.reason,
            {},
            config.model_dump(mode="json"),
        )
        from gis.provider_control.binding import reconcile_schedules

        reconcile_schedules(self.session, policy)
        self.session.flush()
        return {"preview": preview, "configuration": self.read(tenant_id, site_id, key)}
