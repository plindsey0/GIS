from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.collection_planning.analysis import (
    CADENCE_POLICY_VERSION,
    CRON_BY_CADENCE,
    DEFAULT_WEIGHTS,
    PRIORITY_POLICY_KEY,
    PRIORITY_POLICY_VERSION,
    RUNS_PER_MONTH,
    cadence_for,
    desired_status,
    digest,
    priority_tier,
    score_components,
)
from gis.integrations.authority_intelligence.analysis import normalize_domain
from gis.integrations.content_intelligence.extraction import normalize_url
from gis.integrations.external_search.scope import country_scope
from gis.integrations.serp.service import normalize_query
from gis.models import (
    AssetLayer,
    AssetType,
    BudgetDecision,
    CollectionBlocker,
    CollectionCadence,
    CollectionOverrideType,
    CollectionPlanItem,
    CollectionPlanningDecision,
    CollectionPlanningPolicy,
    CollectionPlanningRun,
    CollectionPriorityTier,
    CollectionTarget,
    CollectionTargetEvidence,
    CollectionTargetOverride,
    CollectionTargetStatus,
    CollectionTargetType,
    CollectorCapability,
    ConnectionStatus,
    CostBudget,
    DataRightsPolicy,
    DataSourceConnection,
    EventSemanticClass,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    GSCSearchObservation,
    MarketDefinition,
    MarketDefinitionMember,
    MarketMemberType,
    MarketObservation,
    MarketParticipantObservation,
    PermittedUse,
    PipelineDefinition,
    RightsStatus,
    ScheduleDefinition,
    ScheduledTarget,
    ScheduleStatus,
    SerpObservation,
    SerpResult,
    Site,
)
from gis.orchestration.schedule import next_occurrence
from gis.provenance.lineage import register_asset, register_lineage
from gis.provenance.service import evaluate_connection_use, evaluate_policy_use

MAX_DISCOVERY_ROWS = 10_000


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_target(target_type: CollectionTargetType, value: str) -> tuple[str, dict[str, str]]:
    if target_type is CollectionTargetType.QUERY:
        normalized = normalize_query(value)
        if not normalized:
            raise ValueError("query target is empty after normalization")
        return normalized, {}
    if target_type is CollectionTargetType.DOMAIN:
        return normalize_domain(value), {}
    if target_type is CollectionTargetType.URL:
        normalized, domain, path = normalize_url(value)
        return normalized, {"domain": domain, "path": path}
    normalized = " ".join(value.casefold().split())
    if not normalized:
        raise ValueError("topic target is empty after normalization")
    return normalized, {}


class CollectionPlanningService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_policy(self, tenant_id: uuid.UUID) -> CollectionPlanningPolicy:
        policy = self.session.scalar(
            select(CollectionPlanningPolicy).where(
                CollectionPlanningPolicy.tenant_id == tenant_id,
                CollectionPlanningPolicy.policy_key == PRIORITY_POLICY_KEY,
                CollectionPlanningPolicy.policy_version == PRIORITY_POLICY_VERSION,
            )
        )
        if policy:
            return policy
        policy = CollectionPlanningPolicy(
            tenant_id=tenant_id,
            policy_key=PRIORITY_POLICY_KEY,
            policy_version=PRIORITY_POLICY_VERSION,
            weights_json={key: str(value) for key, value in DEFAULT_WEIGHTS.items()},
            thresholds_json={
                "activate": "0.65",
                "reactivate": "0.70",
                "dormant": "0.35",
                "minimum_evidence": 2,
            },
            cadence_json={
                "version": CADENCE_POLICY_VERSION,
                "critical": "DAILY",
                "high": "MULTIPLE_PER_WEEK",
                "medium": "WEEKLY",
                "low": "MONTHLY",
                "discovery": "ON_DEMAND",
                "dormant": "NONE",
            },
            description="Deterministic evidence-value priority and hysteresis policy.",
        )
        self.session.add(policy)
        self.session.flush()
        return policy

    def ensure_lineage(self) -> None:
        evidence = register_asset(
            self.session,
            "gis_core.collection_target_evidence",
            AssetType.EVIDENCE,
            AssetLayer.CORE,
            description="Normalized evidence supporting scoped collection targets.",
        )
        decision = register_asset(
            self.session,
            "gis_core.collection_planning_decision",
            AssetType.EVIDENCE,
            AssetLayer.CORE,
            description="Immutable deterministic collection-planning evaluations.",
        )
        plan = register_asset(
            self.session,
            "gis_core.collection_plan_item",
            AssetType.EVIDENCE,
            AssetLayer.CORE,
            description="Desired target-by-collector collection state.",
        )
        scheduled = register_asset(
            self.session,
            "gis_core.scheduled_target",
            AssetType.TABLE,
            AssetLayer.CORE,
        )
        for source in (
            "gis_raw.gsc_search_observation",
            "gis_raw.serp_observation",
            "gis_raw.external_search_observation",
            "gis_raw.competitive_content_observation",
            "gis_raw.technology_observation",
            "gis_raw.authority_observation",
            "gis_core.competitive_event",
            "gis_raw.market_observation",
        ):
            upstream = register_asset(
                self.session,
                source,
                AssetType.TABLE,
                AssetLayer.RAW if source.startswith("gis_raw") else AssetLayer.CORE,
            )
            register_lineage(self.session, upstream, evidence, reference=PRIORITY_POLICY_VERSION)
        register_lineage(self.session, evidence, decision, reference=PRIORITY_POLICY_VERSION)
        register_lineage(self.session, decision, plan, reference=CADENCE_POLICY_VERSION)
        register_lineage(self.session, plan, scheduled, reference="explicit apply")

    def ensure_collectors(self) -> list[CollectorCapability]:
        specifications = (
            ("SERP", "serp", CollectionTargetType.QUERY, "SERP_OBSERVATION", 10),
            (
                "EXTERNAL_SEARCH_QUERY",
                "external_search",
                CollectionTargetType.QUERY,
                "EXTERNAL_KEYWORD",
                20,
            ),
            (
                "EXTERNAL_SEARCH_DOMAIN",
                "external_search",
                CollectionTargetType.DOMAIN,
                "DOMAIN_KEYWORDS",
                10,
            ),
            (
                "TECHNOLOGY_DOMAIN",
                "competitive_technology",
                CollectionTargetType.DOMAIN,
                "TECHNOLOGY_PROFILE",
                30,
            ),
            (
                "AUTHORITY_DOMAIN",
                "authority_intelligence",
                CollectionTargetType.DOMAIN,
                "AUTHORITY_PROFILE",
                20,
            ),
            (
                "CONTENT_URL",
                "competitive_content",
                CollectionTargetType.URL,
                "CONTENT_OBSERVATION",
                10,
            ),
            (
                "TECHNOLOGY_URL",
                "competitive_technology",
                CollectionTargetType.URL,
                "TECHNOLOGY_PROFILE",
                30,
            ),
            (
                "EXPERIENCE_URL",
                "experience",
                CollectionTargetType.URL,
                "EXPERIENCE_OBSERVATION",
                40,
            ),
        )
        rows: list[CollectorCapability] = []
        for key, pipeline_key, target_type, product, preference in specifications:
            pipeline = self.session.scalar(
                select(PipelineDefinition).where(PipelineDefinition.key == pipeline_key)
            )
            if not pipeline:
                continue
            row = self.session.scalar(
                select(CollectorCapability).where(
                    CollectorCapability.capability_key == key,
                    CollectorCapability.target_type == target_type,
                )
            )
            if not row:
                row = CollectorCapability(
                    capability_key=key,
                    pipeline_id=pipeline.id,
                    target_type=target_type,
                    evidence_product=product,
                    estimated_cost_per_run=(
                        None
                        if pipeline.paid_provider and pipeline.default_estimated_cost == 0
                        else pipeline.default_estimated_cost
                    ),
                    currency=pipeline.currency,
                    preference=preference,
                    configuration_json={"provider_neutral": True},
                )
                self.session.add(row)
                self.session.flush()
            rows.append(row)
        return rows

    def _validate_market(self, market: MarketDefinition) -> Site:
        site = self.session.scalar(
            select(Site).where(Site.tenant_id == market.tenant_id, Site.id == market.site_id)
        )
        if not site:
            raise ValueError("market is outside a valid tenant/site scope")
        return site

    def register_target(
        self,
        market: MarketDefinition,
        target_type: CollectionTargetType,
        value: str,
        *,
        source_system: str,
        evidence_type: str,
        evidence_identifier: str,
        evidence_at: datetime,
        semantic_class: EventSemanticClass,
        signal_name: str,
        signal_value: Decimal | None,
        human_managed: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> CollectionTarget:
        self._validate_market(market)
        normalized, normalized_metadata = normalize_target(target_type, value)
        context = {
            "country_code": market.country_code
            if target_type is CollectionTargetType.QUERY
            else None,
            "language_code": market.language_code
            if target_type is CollectionTargetType.QUERY
            else None,
            "device": market.device if target_type is CollectionTargetType.QUERY else None,
        }
        identity_hash = digest([market.id, market.version, target_type.value, normalized, context])
        target = self.session.scalar(
            select(CollectionTarget).where(
                CollectionTarget.tenant_id == market.tenant_id,
                CollectionTarget.site_id == market.site_id,
                CollectionTarget.identity_hash == identity_hash,
            )
        )
        if not target:
            target = CollectionTarget(
                tenant_id=market.tenant_id,
                site_id=market.site_id,
                market_definition_id=market.id,
                market_definition_version=market.version,
                target_type=target_type,
                normalized_identity=normalized,
                identity_hash=identity_hash,
                display_value=value.strip(),
                status=CollectionTargetStatus.CANDIDATE,
                discovered_at=evidence_at,
                human_managed=human_managed,
                provenance_metadata={"initial_source": source_system},
                metadata_json={**normalized_metadata, **(metadata or {})},
                **context,
            )
            self.session.add(target)
            self.session.flush()
        evidence = self.session.scalar(
            select(CollectionTargetEvidence).where(
                CollectionTargetEvidence.target_id == target.id,
                CollectionTargetEvidence.source_system == source_system,
                CollectionTargetEvidence.evidence_type == evidence_type,
                CollectionTargetEvidence.evidence_identifier == evidence_identifier,
            )
        )
        if not evidence:
            self.session.add(
                CollectionTargetEvidence(
                    target_id=target.id,
                    source_system=source_system,
                    evidence_type=evidence_type,
                    evidence_identifier=evidence_identifier,
                    evidence_at=evidence_at,
                    semantic_class=semantic_class,
                    signal_name=signal_name,
                    signal_value=signal_value,
                    metadata_json=metadata or {},
                )
            )
        return target

    def seed_target(
        self,
        market: MarketDefinition,
        target_type: CollectionTargetType,
        value: str,
        actor: str,
        reason: str,
    ) -> CollectionTarget:
        return self.register_target(
            market,
            target_type,
            value,
            source_system="HUMAN",
            evidence_type="OPERATOR_SEED",
            evidence_identifier=digest([actor, reason, target_type.value, value]),
            evidence_at=utcnow(),
            semantic_class=EventSemanticClass.HEURISTIC,
            signal_name="strategic_seed",
            signal_value=Decimal(1),
            human_managed=True,
            metadata={"actor": actor, "reason": reason, "semantic": "HUMAN_SUPPLIED"},
        )

    def discover(self, market: MarketDefinition) -> list[CollectionTarget]:
        self._validate_market(market)
        discovered: dict[uuid.UUID, CollectionTarget] = {}
        members = self.session.scalars(
            select(MarketDefinitionMember)
            .where(
                MarketDefinitionMember.market_definition_id == market.id,
                MarketDefinitionMember.member_type == MarketMemberType.TRACKED_QUERY,
            )
            .limit(MAX_DISCOVERY_ROWS)
        ).all()
        query_ids = [item.member_uuid for item in members if item.member_uuid]
        for member in members:
            target = self.register_target(
                market,
                CollectionTargetType.QUERY,
                member.member_key,
                source_system="MARKET_INTELLIGENCE",
                evidence_type="MARKET_MEMBER",
                evidence_identifier=str(member.id),
                evidence_at=member.created_at,
                semantic_class=EventSemanticClass.GIS_DERIVED,
                signal_name="market_relevance",
                signal_value=Decimal(1),
            )
            discovered[target.id] = target
        for row in self.session.scalars(
            select(GSCSearchObservation)
            .where(
                GSCSearchObservation.tenant_id == market.tenant_id,
                GSCSearchObservation.site_id == market.site_id,
                GSCSearchObservation.query.is_not(None),
                GSCSearchObservation.effective_end.is_(None),
            )
            .limit(MAX_DISCOVERY_ROWS)
        ):
            assert row.query is not None
            target = self.register_target(
                market,
                CollectionTargetType.QUERY,
                row.query,
                source_system="GSC",
                evidence_type="QUERY_OBSERVATION",
                evidence_identifier=str(row.id),
                evidence_at=row.observed_at,
                semantic_class=EventSemanticClass.MEASURED,
                signal_name="owned_site_signal",
                signal_value=min(Decimal(1), row.impressions / Decimal(1000)),
                metadata={"impressions": str(row.impressions), "clicks": str(row.clicks)},
            )
            discovered[target.id] = target
        external_rows = self.session.execute(
            select(ExternalKeywordRanking, ExternalSearchObservation)
            .join(
                ExternalSearchObservation,
                ExternalSearchObservation.id
                == ExternalKeywordRanking.external_search_observation_id,
            )
            .where(
                ExternalSearchObservation.tenant_id == market.tenant_id,
                ExternalSearchObservation.site_id == market.site_id,
                ExternalSearchObservation.effective_end.is_(None),
                country_scope(market.country_code),
                ExternalSearchObservation.language_code == market.language_code,
                ExternalSearchObservation.device == market.device,
            )
            .order_by(
                ExternalSearchObservation.observed_at,
                ExternalKeywordRanking.normalized_keyword,
                ExternalKeywordRanking.id,
            )
            .limit(MAX_DISCOVERY_ROWS)
        ).all()
        for keyword, parent in external_rows:
            policy = self.session.get(DataRightsPolicy, parent.rights_policy_id)
            rights = evaluate_policy_use(self.session, policy, PermittedUse.DERIVATIVE_CREATION)
            if rights.status is not RightsStatus.ALLOWED:
                continue
            target = self.register_target(
                market,
                CollectionTargetType.QUERY,
                keyword.keyword,
                source_system="EXTERNAL_SEARCH",
                evidence_type="EXTERNAL_KEYWORD_RANKING",
                evidence_identifier=str(keyword.id),
                evidence_at=parent.observed_at,
                semantic_class=EventSemanticClass.PROVIDER_REPORTED,
                signal_name="competitor_signal",
                signal_value=Decimal("0.70"),
                metadata={
                    "external_search_observation_id": str(parent.id),
                    "ranking_domain": keyword.ranking_domain,
                    "position": keyword.position,
                    "rights_policy_id": str(parent.rights_policy_id),
                },
            )
            discovered[target.id] = target
        observations = self.session.scalars(
            select(SerpObservation)
            .where(
                SerpObservation.tenant_id == market.tenant_id,
                SerpObservation.site_id == market.site_id,
                SerpObservation.tracked_query_id.in_(query_ids),
                SerpObservation.effective_end.is_(None),
            )
            .limit(MAX_DISCOVERY_ROWS)
        ).all()
        observation_ids = [item.id for item in observations]
        observation_at = {item.id: item.observed_at for item in observations}
        if observation_ids:
            for result in self.session.scalars(
                select(SerpResult)
                .where(
                    SerpResult.serp_observation_id.in_(observation_ids),
                    SerpResult.is_organic.is_(True),
                )
                .limit(MAX_DISCOVERY_ROWS)
            ):
                if result.hostname:
                    target = self.register_target(
                        market,
                        CollectionTargetType.DOMAIN,
                        result.hostname,
                        source_system="SERP",
                        evidence_type="ORGANIC_PARTICIPANT",
                        evidence_identifier=str(result.id),
                        evidence_at=observation_at[result.serp_observation_id],
                        semantic_class=EventSemanticClass.MEASURED,
                        signal_name="competitor_signal",
                        signal_value=Decimal("0.70"),
                        metadata={"rank": result.rank_absolute},
                    )
                    discovered[target.id] = target
                if result.normalized_url:
                    target = self.register_target(
                        market,
                        CollectionTargetType.URL,
                        result.normalized_url,
                        source_system="SERP",
                        evidence_type="RANKING_URL",
                        evidence_identifier=str(result.id),
                        evidence_at=observation_at[result.serp_observation_id],
                        semantic_class=EventSemanticClass.MEASURED,
                        signal_name="competitor_signal",
                        signal_value=Decimal("0.60"),
                        metadata={"rank": result.rank_absolute},
                    )
                    discovered[target.id] = target
        market_observation_ids = self.session.scalars(
            select(MarketObservation.id).where(
                MarketObservation.market_definition_id == market.id,
                MarketObservation.effective_end.is_(None),
            )
        ).all()
        if market_observation_ids:
            for participant in self.session.scalars(
                select(MarketParticipantObservation)
                .where(
                    MarketParticipantObservation.market_observation_id.in_(market_observation_ids)
                )
                .limit(MAX_DISCOVERY_ROWS)
            ):
                target = self.register_target(
                    market,
                    CollectionTargetType.DOMAIN,
                    participant.domain,
                    source_system="MARKET_INTELLIGENCE",
                    evidence_type="MARKET_PARTICIPANT",
                    evidence_identifier=str(participant.id),
                    evidence_at=participant.last_observed_at,
                    semantic_class=EventSemanticClass.GIS_DERIVED,
                    signal_name="market_relevance",
                    signal_value=participant.query_overlap_rate,
                )
                discovered[target.id] = target
        self.session.flush()
        return list(discovered.values())

    def _components(self, target: CollectionTarget) -> tuple[dict[str, Decimal | None], int]:
        rows = self.session.scalars(
            select(CollectionTargetEvidence).where(CollectionTargetEvidence.target_id == target.id)
        ).all()
        grouped: dict[str, list[Decimal]] = defaultdict(list)
        for row in rows:
            if row.signal_value is not None:
                grouped[row.signal_name].append(row.signal_value)
        components: dict[str, Decimal | None] = {
            key: max(grouped[key]) if grouped[key] else None for key in DEFAULT_WEIGHTS
        }
        active_scheduled = self.session.scalar(
            select(func.count())
            .select_from(ScheduledTarget)
            .where(
                ScheduledTarget.tenant_id == target.tenant_id,
                ScheduledTarget.site_id == target.site_id,
                ScheduledTarget.target_type == target.target_type.value,
                ScheduledTarget.target_key == target.normalized_identity,
                ScheduledTarget.active.is_(True),
            )
        )
        components["information_gap"] = Decimal(0) if active_scheduled else Decimal(1)
        return components, len(rows)

    def _active_override(self, target_id: uuid.UUID) -> CollectionTargetOverride | None:
        return self.session.scalar(
            select(CollectionTargetOverride).where(
                CollectionTargetOverride.target_id == target_id,
                CollectionTargetOverride.active.is_(True),
            )
        )

    def _connection(
        self, target: CollectionTarget, capability: CollectorCapability
    ) -> DataSourceConnection | None:
        pipeline = self.session.get(PipelineDefinition, capability.pipeline_id)
        if not pipeline or not pipeline.data_source_id:
            return None
        return self.session.scalar(
            select(DataSourceConnection).where(
                DataSourceConnection.tenant_id == target.tenant_id,
                DataSourceConnection.site_id == target.site_id,
                DataSourceConnection.data_source_id == pipeline.data_source_id,
                DataSourceConnection.status == ConnectionStatus.ACTIVE,
            )
        )

    def _budget(
        self, target: CollectionTarget, capability: CollectorCapability, monthly: Decimal | None
    ) -> tuple[BudgetDecision, str]:
        if monthly is None:
            return BudgetDecision.BLOCK, "provider cost is unknown"
        pipeline = self.session.get(PipelineDefinition, capability.pipeline_id)
        budgets = self.session.scalars(
            select(CostBudget).where(
                CostBudget.tenant_id == target.tenant_id, CostBudget.active.is_(True)
            )
        ).all()
        for budget in budgets:
            if budget.site_id and budget.site_id != target.site_id:
                continue
            if budget.pipeline_id and budget.pipeline_id != capability.pipeline_id:
                continue
            if budget.data_source_id and (
                not pipeline or budget.data_source_id != pipeline.data_source_id
            ):
                continue
            if budget.currency != capability.currency:
                return BudgetDecision.BLOCK, "budget currency differs from collector currency"
            if (
                budget.per_run_limit is not None
                and capability.estimated_cost_per_run is not None
                and capability.estimated_cost_per_run > budget.per_run_limit
            ):
                return BudgetDecision.BLOCK, "estimated run cost exceeds per-run budget"
            if budget.monthly_limit is not None and monthly > budget.monthly_limit:
                return BudgetDecision.BLOCK, "forecast exceeds monthly budget"
        return BudgetDecision.ALLOW, "within configured planning budgets"

    def plan(self, market: MarketDefinition) -> CollectionPlanningRun:
        self._validate_market(market)
        self.ensure_lineage()
        policy = self.ensure_policy(market.tenant_id)
        capabilities = self.ensure_collectors()
        targets = self.session.scalars(
            select(CollectionTarget)
            .where(
                CollectionTarget.tenant_id == market.tenant_id,
                CollectionTarget.site_id == market.site_id,
                CollectionTarget.market_definition_id == market.id,
            )
            .order_by(CollectionTarget.identity_hash)
            .limit(MAX_DISCOVERY_ROWS)
        ).all()
        state = []
        for target in targets:
            evidence_ids = self.session.scalars(
                select(CollectionTargetEvidence.id)
                .where(CollectionTargetEvidence.target_id == target.id)
                .order_by(CollectionTargetEvidence.id)
            ).all()
            override = self._active_override(target.id)
            state.append(
                [target.id, target.status.value, evidence_ids, override.id if override else None]
            )
        fingerprint = digest(
            [
                market.id,
                market.version,
                policy.policy_version,
                state,
                [(item.id, item.active, item.estimated_cost_per_run) for item in capabilities],
            ]
        )
        existing = self.session.scalar(
            select(CollectionPlanningRun).where(
                CollectionPlanningRun.tenant_id == market.tenant_id,
                CollectionPlanningRun.site_id == market.site_id,
                CollectionPlanningRun.fingerprint == fingerprint,
            )
        )
        if existing:
            return existing
        now = utcnow()
        run = CollectionPlanningRun(
            tenant_id=market.tenant_id,
            site_id=market.site_id,
            market_definition_id=market.id,
            market_definition_version=market.version,
            policy_id=policy.id,
            policy_version=policy.policy_version,
            evaluated_at=now,
            fingerprint=fingerprint,
            target_count=len(targets),
            metadata_json={"provider_calls": 0, "cadence_policy": CADENCE_POLICY_VERSION},
        )
        self.session.add(run)
        self.session.flush()
        total_monthly = Decimal(0)
        has_unknown_cost = False
        for target in targets:
            components, evidence_count = self._components(target)
            score, unknowns = score_components(components)
            tier = priority_tier(score, evidence_count)
            computed = desired_status(target.status, score, evidence_count)
            cadence = cadence_for(tier)
            override = self._active_override(target.id)
            effective_status, effective_cadence, effective_tier = computed, cadence, tier
            override_applied = False
            if override:
                override_applied = True
                if override.override_type is CollectionOverrideType.FORCE_ACTIVE:
                    effective_status = CollectionTargetStatus.ACTIVE
                elif override.override_type is CollectionOverrideType.FORCE_PAUSED:
                    effective_status = CollectionTargetStatus.PAUSED
                elif override.override_type is CollectionOverrideType.FORCE_RETIRED:
                    effective_status = CollectionTargetStatus.RETIRED
                elif (
                    override.override_type is CollectionOverrideType.FORCE_PRIORITY
                    and override.forced_priority
                ):
                    effective_tier = override.forced_priority
                    effective_cadence = cadence_for(effective_tier)
                elif (
                    override.override_type is CollectionOverrideType.FORCE_CADENCE
                    and override.forced_cadence
                ):
                    effective_cadence = override.forced_cadence
            target_capabilities = [
                item
                for item in capabilities
                if item.target_type is target.target_type and item.active
            ]
            blockers: list[CollectionBlocker] = []
            if evidence_count < 2:
                blockers.append(CollectionBlocker.INSUFFICIENT_EVIDENCE)
            if not target_capabilities:
                blockers.append(CollectionBlocker.NO_PROVIDER)
            decision = CollectionPlanningDecision(
                planning_run_id=run.id,
                target_id=target.id,
                policy_version=policy.policy_version,
                priority_score=score,
                priority_tier=effective_tier,
                component_scores={
                    key: str(value) if value is not None else None
                    for key, value in components.items()
                },
                unknown_components=unknowns,
                computed_status=computed,
                effective_status=effective_status,
                computed_cadence=cadence,
                effective_cadence=effective_cadence,
                primary_blocker=blockers[0] if blockers else CollectionBlocker.NONE,
                blockers_json=[item.value for item in blockers],
                override_applied=override_applied,
                explanation_json={
                    "evidence_count": evidence_count,
                    "formula": PRIORITY_POLICY_VERSION,
                    "unknown_is_zero": False,
                },
                evaluated_at=now,
            )
            self.session.add(decision)
            self.session.flush()
            eligible_items = 0
            for capability in target_capabilities:
                if (
                    override
                    and override.override_type is CollectionOverrideType.FORCE_COLLECTOR
                    and override.forced_capability_id != capability.id
                ):
                    continue
                connection = self._connection(target, capability)
                pipeline = self.session.get(PipelineDefinition, capability.pipeline_id)
                rights = RightsStatus.UNKNOWN
                rights_reason = "no configured connection"
                if connection:
                    evaluation = evaluate_connection_use(
                        self.session, connection, PermittedUse.NORMALIZED_RETENTION
                    )
                    rights, rights_reason = evaluation.status, evaluation.reason
                runs = RUNS_PER_MONTH[effective_cadence]
                monthly = (
                    capability.estimated_cost_per_run * runs
                    if capability.estimated_cost_per_run is not None
                    else None
                )
                budget, budget_reason = self._budget(target, capability, monthly)
                blocker = CollectionBlocker.NONE
                if rights is not RightsStatus.ALLOWED:
                    blocker = CollectionBlocker.BLOCKED_BY_RIGHTS
                elif monthly is None:
                    blocker = CollectionBlocker.UNKNOWN_COST
                elif budget is BudgetDecision.BLOCK:
                    blocker = CollectionBlocker.BUDGET_BLOCKED
                if blocker is not CollectionBlocker.NONE and blocker not in blockers:
                    blockers.append(blocker)
                if blocker is CollectionBlocker.NONE:
                    eligible_items += 1
                item_cadence = (
                    effective_cadence
                    if blocker is CollectionBlocker.NONE
                    else CollectionCadence.NONE
                )
                self.session.add(
                    CollectionPlanItem(
                        decision_id=decision.id,
                        collector_capability_id=capability.id,
                        data_source_connection_id=connection.id if connection else None,
                        desired_cadence=effective_cadence,
                        effective_cadence=item_cadence,
                        rights_status=rights,
                        budget_decision=budget,
                        estimated_cost_per_run=capability.estimated_cost_per_run,
                        estimated_runs_month=runs,
                        estimated_monthly_cost=monthly,
                        currency=capability.currency,
                        blocker=blocker,
                        explanation_json={
                            "rights": rights_reason,
                            "budget": budget_reason,
                            "pipeline": pipeline.key if pipeline else None,
                        },
                    )
                )
                if monthly is None:
                    has_unknown_cost = True
                else:
                    total_monthly += monthly
            if blockers:
                decision.blockers_json = [item.value for item in blockers]
                decision.primary_blocker = CollectionBlocker.NONE if eligible_items else blockers[0]
                if (
                    decision.effective_status is CollectionTargetStatus.ACTIVE
                    and eligible_items == 0
                ):
                    decision.effective_status = CollectionTargetStatus.PAUSED
                    decision.effective_cadence = CollectionCadence.NONE
        run.proposed_monthly_cost = None if has_unknown_cost else total_monthly
        self.session.flush()
        return run

    def apply(self, run: CollectionPlanningRun, actor: str) -> list[CollectionPlanItem]:
        site = self.session.get(Site, run.site_id)
        if not site or site.tenant_id != run.tenant_id:
            raise ValueError("planning run is outside tenant/site scope")
        applied: list[CollectionPlanItem] = []
        decisions = self.session.scalars(
            select(CollectionPlanningDecision).where(
                CollectionPlanningDecision.planning_run_id == run.id
            )
        ).all()
        for decision in decisions:
            target = self.session.get(CollectionTarget, decision.target_id)
            assert target is not None
            target.status = decision.effective_status
            target.current_policy_version = decision.policy_version
            now = utcnow()
            if target.status is CollectionTargetStatus.ACTIVE and not target.activated_at:
                target.activated_at = now
            elif target.status is CollectionTargetStatus.PAUSED:
                target.paused_at = now
            elif target.status is CollectionTargetStatus.DORMANT:
                target.dormant_at = now
            elif target.status is CollectionTargetStatus.RETIRED:
                target.retired_at = now
            for item in self.session.scalars(
                select(CollectionPlanItem).where(CollectionPlanItem.decision_id == decision.id)
            ):
                capability = self.session.get(CollectorCapability, item.collector_capability_id)
                assert capability is not None
                schedule_name = f"Planner {capability.capability_key} {item.desired_cadence.value}"
                schedule = self.session.scalar(
                    select(ScheduleDefinition).where(
                        ScheduleDefinition.tenant_id == run.tenant_id,
                        ScheduleDefinition.name == schedule_name,
                    )
                )
                if not schedule:
                    schedule = ScheduleDefinition(
                        tenant_id=run.tenant_id,
                        organization_id=site.organization_id,
                        site_id=site.id,
                        pipeline_id=capability.pipeline_id,
                        data_source_connection_id=item.data_source_connection_id,
                        name=schedule_name,
                        cron_expression=CRON_BY_CADENCE[item.desired_cadence],
                        timezone=site.timezone,
                        status=ScheduleStatus.DISABLED,
                        max_attempts=3,
                        retry_delay_seconds=300,
                        exponential_backoff=True,
                        configuration_json={
                            "planner_managed": True,
                            "requires_operator_activation": True,
                        },
                    )
                    schedule.next_scheduled_at = next_occurrence(
                        schedule.cron_expression, schedule.timezone, now
                    )
                    self.session.add(schedule)
                    self.session.flush()
                scheduled = self.session.scalar(
                    select(ScheduledTarget).where(
                        ScheduledTarget.schedule_id == schedule.id,
                        ScheduledTarget.target_type == target.target_type.value,
                        ScheduledTarget.target_key == target.normalized_identity,
                    )
                )
                active = (
                    decision.effective_status is CollectionTargetStatus.ACTIVE
                    and item.blocker is CollectionBlocker.NONE
                )
                if not scheduled:
                    scheduled = ScheduledTarget(
                        tenant_id=target.tenant_id,
                        site_id=target.site_id,
                        schedule_id=schedule.id,
                        target_type=target.target_type.value,
                        target_key=target.normalized_identity,
                        active=active,
                        configuration_json={
                            "planning_decision_id": str(decision.id),
                            "applied_by": actor,
                        },
                    )
                    self.session.add(scheduled)
                    self.session.flush()
                else:
                    scheduled.active = active
                    scheduled.configuration_json = {
                        **scheduled.configuration_json,
                        "planning_decision_id": str(decision.id),
                        "applied_by": actor,
                    }
                item.scheduled_target_id = scheduled.id
                item.applied_at = now
                applied.append(item)
        self.session.flush()
        return applied

    def explain(self, target: CollectionTarget) -> dict[str, Any]:
        decision = self.session.scalar(
            select(CollectionPlanningDecision)
            .where(CollectionPlanningDecision.target_id == target.id)
            .order_by(CollectionPlanningDecision.evaluated_at.desc())
        )
        evidence = self.session.scalars(
            select(CollectionTargetEvidence)
            .where(CollectionTargetEvidence.target_id == target.id)
            .order_by(CollectionTargetEvidence.evidence_at.desc())
        ).all()
        override = self._active_override(target.id)
        items = (
            self.session.scalars(
                select(CollectionPlanItem).where(CollectionPlanItem.decision_id == decision.id)
            ).all()
            if decision
            else []
        )
        return {
            "target_id": target.id,
            "target": target.display_value,
            "normalized_identity": target.normalized_identity,
            "target_type": target.target_type,
            "market_definition_id": target.market_definition_id,
            "market_definition_version": target.market_definition_version,
            "status": target.status,
            "priority": decision.priority_tier if decision else None,
            "priority_score": decision.priority_score if decision else None,
            "policy_version": decision.policy_version if decision else None,
            "computed_status": decision.computed_status if decision else None,
            "effective_status": decision.effective_status if decision else None,
            "reasons": [
                {
                    "signal": row.signal_name,
                    "value": row.signal_value,
                    "source": row.source_system,
                    "evidence": row.evidence_identifier,
                    "semantic_class": row.semantic_class,
                }
                for row in evidence
            ],
            "unknown_signals": decision.unknown_components if decision else [],
            "collection": [
                {
                    "capability_id": item.collector_capability_id,
                    "cadence": item.effective_cadence,
                    "estimated_monthly_cost": item.estimated_monthly_cost,
                    "rights": item.rights_status,
                    "budget": item.budget_decision,
                    "blocker": item.blocker,
                }
                for item in items
            ],
            "blockers": decision.blockers_json if decision else [],
            "override": {
                "type": override.override_type,
                "actor": override.actor,
                "reason": override.reason,
            }
            if override
            else None,
        }

    def set_override(
        self,
        target: CollectionTarget,
        override_type: CollectionOverrideType,
        actor: str,
        reason: str,
        *,
        priority: CollectionPriorityTier | None = None,
        cadence: CollectionCadence | None = None,
        capability_id: uuid.UUID | None = None,
    ) -> CollectionTargetOverride:
        current = self._active_override(target.id)
        if current:
            current.active = False
            current.cleared_at = utcnow()
            current.cleared_by = actor
        row = CollectionTargetOverride(
            target_id=target.id,
            override_type=override_type,
            forced_priority=priority,
            forced_cadence=cadence,
            forced_capability_id=capability_id,
            actor=actor,
            reason=reason,
            active=True,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def clear_override(
        self, target: CollectionTarget, actor: str
    ) -> CollectionTargetOverride | None:
        current = self._active_override(target.id)
        if current:
            current.active = False
            current.cleared_at = utcnow()
            current.cleared_by = actor
            self.session.flush()
        return current
