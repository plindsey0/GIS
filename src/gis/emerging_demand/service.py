from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.collection_planning.analysis import digest
from gis.emerging_demand.analysis import POLICY_VERSION, Point, classify
from gis.models import (
    AssetLayer,
    AssetType,
    CollectionPriorityTier,
    CollectionTarget,
    CollectionTargetEvidence,
    DataRightsPolicy,
    DemandAnalysisRun,
    DemandCoverageState,
    DemandEntityType,
    DemandEvidenceRole,
    DemandEvidenceStrength,
    DemandObservation,
    DemandSignal,
    DemandSignalEvidence,
    DemandSignalType,
    DemandValidationRequest,
    EventSemanticClass,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    MarketDefinition,
    PermittedUse,
    RightsStatus,
    ValidationRequestStatus,
)
from gis.provenance.lineage import register_asset, register_lineage
from gis.provenance.service import evaluate_policy_use


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def json_value(value: Any) -> Any:
    if isinstance(value, (uuid.UUID, datetime, Decimal)):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value


class EmergingDemandService:
    """Analyze stored, compatible primary demand series without provider calls."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_lineage(self) -> None:
        observation = register_asset(
            self.session,
            "gis_raw.demand_observation",
            AssetType.TABLE,
            AssetLayer.RAW,
            description="Provider-specific, revision-aware observable demand evidence.",
        )
        signal = register_asset(
            self.session,
            "gis_core.demand_signal",
            AssetType.EVIDENCE,
            AssetLayer.CORE,
            description="Versioned deterministic demand dynamics; not opportunity semantics.",
        )
        validation = register_asset(
            self.session,
            "gis_core.demand_validation_request",
            AssetType.EVIDENCE,
            AssetLayer.CORE,
            description="Non-executing evidence request for Collection Planning.",
        )
        planning = register_asset(
            self.session,
            "gis_core.collection_target_evidence",
            AssetType.EVIDENCE,
            AssetLayer.CORE,
        )
        for source_name in (
            "gis_raw.external_search_observation",
            "gis_raw.market_observation",
            "gis_raw.gsc_search_observation",
            "gis_raw.serp_observation",
            "gis_raw.competitive_content_observation",
            "gis_core.collection_target",
            "gis_core.collection_planning_decision",
        ):
            upstream = register_asset(
                self.session,
                source_name,
                AssetType.TABLE,
                AssetLayer.RAW if source_name.startswith("gis_raw") else AssetLayer.CORE,
            )
            register_lineage(self.session, upstream, observation, reference=POLICY_VERSION)
        register_lineage(self.session, observation, signal, reference=POLICY_VERSION)
        register_lineage(self.session, signal, validation, reference="planning validation input")
        register_lineage(self.session, signal, planning, reference="planning evidence only")

    def _scope(
        self, tenant_id: uuid.UUID, site_id: uuid.UUID, market_id: uuid.UUID
    ) -> MarketDefinition:
        market = self.session.scalar(
            select(MarketDefinition).where(
                MarketDefinition.id == market_id,
                MarketDefinition.tenant_id == tenant_id,
                MarketDefinition.site_id == site_id,
            )
        )
        if not market:
            raise ValueError("market does not belong to the tenant/site scope")
        return market

    @staticmethod
    def series_key(observation: DemandObservation) -> str:
        return digest(
            {
                "entity": observation.entity_key,
                "source": observation.source_system,
                "metric": observation.source_metric,
                "unit": observation.unit,
                "resolution_days": observation.resolution_days,
                "country": observation.country_code,
                "language": observation.language_code,
                "device": observation.device,
                "method": observation.method_key,
                "method_version": observation.method_version,
                "market_version": observation.market_definition_version,
            }
        )

    def _rights_allowed(self, observation: DemandObservation) -> bool:
        policy = self.session.get(DataRightsPolicy, observation.rights_policy_id)
        evaluation = evaluate_policy_use(self.session, policy, PermittedUse.DERIVATIVE_CREATION)
        return evaluation.status is RightsStatus.ALLOWED

    def materialize_stored_evidence(self, market: MarketDefinition) -> int:
        """Normalize already-stored provider volume without external retrieval."""
        targets = self.session.scalars(
            select(CollectionTarget).where(
                CollectionTarget.tenant_id == market.tenant_id,
                CollectionTarget.site_id == market.site_id,
                CollectionTarget.market_definition_id == market.id,
                CollectionTarget.market_definition_version == market.version,
            )
        ).all()
        by_query = {target.normalized_identity: target for target in targets}
        rows = self.session.execute(
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
                ExternalKeywordRanking.search_volume.is_not(None),
            )
            .order_by(ExternalSearchObservation.observed_date, ExternalKeywordRanking.id)
        ).all()
        created = 0
        seen: set[str] = set()
        for keyword, parent in rows:
            target = by_query.get(keyword.normalized_keyword)
            if not target:
                continue
            policy = self.session.get(DataRightsPolicy, parent.rights_policy_id)
            rights = evaluate_policy_use(self.session, policy, PermittedUse.DERIVATIVE_CREATION)
            if rights.status is not RightsStatus.ALLOWED:
                continue
            identity = digest(
                {
                    "target": str(target.id),
                    "date": parent.observed_date,
                    "source": "external_search",
                    "metric": "PROVIDER_SEARCH_VOLUME",
                    "country": parent.country_code,
                    "language": parent.language_code,
                    "device": parent.device,
                }
            )
            if identity in seen:
                continue
            seen.add(identity)
            content_hash = digest(
                {
                    "parent": parent.content_hash,
                    "volume": keyword.search_volume,
                    "keyword": keyword.normalized_keyword,
                }
            )
            current = self.session.scalar(
                select(DemandObservation).where(
                    DemandObservation.observation_key == identity,
                    DemandObservation.effective_end.is_(None),
                )
            )
            if current and current.content_hash == content_hash:
                continue
            now = utcnow()
            if current:
                current.effective_end = now
            self.session.add(
                DemandObservation(
                    tenant_id=market.tenant_id,
                    site_id=market.site_id,
                    market_definition_id=market.id,
                    market_definition_version=market.version,
                    collection_target_id=target.id,
                    entity_type=DemandEntityType.QUERY,
                    entity_key=target.normalized_identity,
                    observed_date=parent.observed_date,
                    observed_at=parent.observed_at,
                    source_system="external_search",
                    source_connection_id=parent.data_source_connection_id,
                    source_record_id=str(keyword.id),
                    source_metric="PROVIDER_SEARCH_VOLUME",
                    value=Decimal(keyword.search_volume),
                    unit="provider_searches",
                    resolution_days=28,
                    country_code=parent.country_code,
                    language_code=parent.language_code,
                    device=parent.device,
                    semantic_class=EventSemanticClass.PROVIDER_REPORTED,
                    coverage_state=DemandCoverageState.OBSERVED,
                    method_key="EXTERNAL_SEARCH_PROVIDER_VOLUME",
                    method_version="1",
                    rights_policy_id=parent.rights_policy_id,
                    observation_key=identity,
                    content_hash=content_hash,
                    provenance_metadata={
                        "external_search_observation_id": str(parent.id),
                        "external_keyword_ranking_id": str(keyword.id),
                        "provider_metric_not_universal_demand": True,
                    },
                    effective_start=now,
                )
            )
            created += 1
        self.session.flush()
        return created

    def analyze(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        market_id: uuid.UUID,
        *,
        analyzed_at: datetime | None = None,
    ) -> DemandAnalysisRun:
        market = self._scope(tenant_id, site_id, market_id)
        self.ensure_lineage()
        now = analyzed_at or utcnow()
        observations = self.session.scalars(
            select(DemandObservation).where(
                DemandObservation.tenant_id == tenant_id,
                DemandObservation.site_id == site_id,
                DemandObservation.market_definition_id == market.id,
                DemandObservation.market_definition_version == market.version,
                DemandObservation.effective_end.is_(None),
            )
        ).all()
        allowed = [item for item in observations if self._rights_allowed(item)]
        fingerprint = digest(
            {
                "policy": POLICY_VERSION,
                "market": str(market.id),
                "version": market.version,
                "evidence": sorted((str(item.id), item.content_hash) for item in allowed),
            }
        )
        existing = self.session.scalar(
            select(DemandAnalysisRun).where(
                DemandAnalysisRun.tenant_id == tenant_id,
                DemandAnalysisRun.site_id == site_id,
                DemandAnalysisRun.fingerprint == fingerprint,
            )
        )
        if existing:
            return existing
        run = DemandAnalysisRun(
            tenant_id=tenant_id,
            site_id=site_id,
            market_definition_id=market.id,
            market_definition_version=market.version,
            policy_version=POLICY_VERSION,
            analyzed_at=now,
            fingerprint=fingerprint,
            observation_count=len(allowed),
            signal_count=0,
            metadata_json={
                "rights_blocked_observations": len(observations) - len(allowed),
                "provider_calls": 0,
            },
        )
        self.session.add(run)
        self.session.flush()
        grouped: dict[str, list[DemandObservation]] = defaultdict(list)
        for observation in allowed:
            grouped[self.series_key(observation)].append(observation)
        for series_key, series in grouped.items():
            series.sort(key=lambda item: item.observed_date)
            target = self.session.get(CollectionTarget, series[-1].collection_target_id)
            regime_changed = bool(
                target
                and target.activated_at
                and target.activated_at.date() >= series[0].observed_date
                and target.activated_at.date() <= series[-1].observed_date
            )
            gaps = [
                (right.observed_date - left.observed_date).days
                for left, right in zip(series, series[1:])
            ]
            continuous = all(
                gap <= max(left.resolution_days * 2, 2) for left, gap in zip(series, gaps)
            )
            result = classify(
                [
                    Point(item.observed_date, item.value)
                    for item in series
                    if item.value is not None
                ],
                continuous=continuous,
                regime_changed=regime_changed,
            )
            coverage = (
                DemandCoverageState.COLLECTION_REGIME_CHANGED
                if regime_changed
                else DemandCoverageState.OBSERVED
                if continuous
                else DemandCoverageState.PARTIAL_COVERAGE
            )
            identity = digest(
                {
                    "run": str(run.id),
                    "series": series_key,
                    "signal": result.signal_type.value,
                    "policy": POLICY_VERSION,
                }
            )
            signal = DemandSignal(
                analysis_run_id=run.id,
                market_definition_id=market.id,
                market_definition_version=market.version,
                collection_target_id=series[-1].collection_target_id,
                entity_type=series[-1].entity_type,
                entity_key=series[-1].entity_key,
                source_series_key=series_key,
                signal_type=result.signal_type,
                window_key=f"{series[-1].resolution_days}D_SERIES",
                window_start=series[0].observed_date,
                window_end=series[-1].observed_date,
                current_value=result.current_value,
                prior_value=result.prior_value,
                absolute_change=result.absolute_change,
                relative_change=result.relative_change,
                velocity=result.velocity,
                prior_velocity=result.prior_velocity,
                acceleration=result.acceleration,
                evidence_strength=result.strength,
                coverage_state=coverage,
                observation_count=len(series),
                collection_regime_changed=regime_changed,
                policy_version=POLICY_VERSION,
                reasons_json=list(result.reasons),
                metrics_json={
                    "unit": series[-1].unit,
                    "source_metric": series[-1].source_metric,
                    "source_system": series[-1].source_system,
                    "resolution_days": series[-1].resolution_days,
                    "normalization": None,
                },
                identity_hash=identity,
            )
            self.session.add(signal)
            self.session.flush()
            for observation in series:
                self.session.add(
                    DemandSignalEvidence(
                        signal_id=signal.id,
                        demand_observation_id=observation.id,
                        role=DemandEvidenceRole.PRIMARY_DEMAND_EVIDENCE,
                        source_system=observation.source_system,
                        evidence_key=str(observation.id),
                        semantic_class=observation.semantic_class,
                        metadata_json={"content_hash": observation.content_hash},
                    )
                )
            self._feedback(signal, target, now)
            run.signal_count += 1
        self.session.flush()
        return run

    def _feedback(
        self, signal: DemandSignal, target: CollectionTarget | None, now: datetime
    ) -> None:
        if not target:
            return
        signal_value = {
            DemandSignalType.EMERGING: Decimal("1"),
            DemandSignalType.ACCELERATING: Decimal("0.9"),
            DemandSignalType.SPIKE: Decimal("0.85"),
            DemandSignalType.FIRST_OBSERVED: Decimal("0.6"),
            DemandSignalType.INSUFFICIENT_HISTORY: Decimal("0.5"),
            DemandSignalType.DECLINING: Decimal("0.2"),
        }.get(signal.signal_type, Decimal("0.4"))
        evidence_identifier = f"demand-signal:{signal.identity_hash}"
        if not self.session.scalar(
            select(CollectionTargetEvidence).where(
                CollectionTargetEvidence.target_id == target.id,
                CollectionTargetEvidence.source_system == "emerging_demand",
                CollectionTargetEvidence.evidence_identifier == evidence_identifier,
            )
        ):
            self.session.add(
                CollectionTargetEvidence(
                    target_id=target.id,
                    source_system="emerging_demand",
                    evidence_type="DEMAND_DYNAMICS",
                    evidence_identifier=evidence_identifier,
                    evidence_at=now,
                    semantic_class=EventSemanticClass.GIS_DERIVED,
                    signal_name="change_signal",
                    signal_value=signal_value,
                    metadata_json={
                        "signal_id": str(signal.id),
                        "signal_type": signal.signal_type.value,
                        "planning_signal_only": True,
                    },
                )
            )
        needs_validation = signal.signal_type in {
            DemandSignalType.FIRST_OBSERVED,
            DemandSignalType.INSUFFICIENT_HISTORY,
            DemandSignalType.SPIKE,
        } and signal.evidence_strength in {
            DemandEvidenceStrength.INSUFFICIENT,
            DemandEvidenceStrength.LIMITED,
        }
        if needs_validation:
            identity = digest({"signal": str(signal.id), "capability": "PRIMARY_DEMAND_EVIDENCE"})
            if not self.session.scalar(
                select(DemandValidationRequest).where(
                    DemandValidationRequest.identity_hash == identity
                )
            ):
                self.session.add(
                    DemandValidationRequest(
                        signal_id=signal.id,
                        collection_target_id=target.id,
                        reason="Additional comparable primary-demand observations are required.",
                        desired_evidence_capability="PRIMARY_DEMAND_EVIDENCE",
                        urgency=CollectionPriorityTier.HIGH
                        if signal.signal_type is DemandSignalType.SPIKE
                        else CollectionPriorityTier.MEDIUM,
                        status=ValidationRequestStatus.OPEN,
                        expires_at=now + timedelta(days=28),
                        identity_hash=identity,
                        provenance_metadata={
                            "originating_signal": str(signal.id),
                            "scheduler_mutation": False,
                            "provider_call": False,
                        },
                    )
                )

    def inspect(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> list[dict[str, Any]]:
        signals = self.session.scalars(
            select(DemandSignal)
            .join(DemandAnalysisRun)
            .where(
                DemandAnalysisRun.tenant_id == tenant_id,
                DemandAnalysisRun.site_id == site_id,
            )
            .order_by(DemandSignal.window_end.desc())
        ).all()
        return [
            {
                "id": signal.id,
                "entity_type": signal.entity_type,
                "entity_key": signal.entity_key,
                "classification": signal.signal_type,
                "evidence_strength": signal.evidence_strength,
                "coverage": signal.coverage_state,
                "current_value": signal.current_value,
                "relative_change": signal.relative_change,
                "velocity": signal.velocity,
                "acceleration": signal.acceleration,
                "newly_observed_is_emerging": False,
            }
            for signal in signals
        ]
