from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.evidence_quality.analysis import (
    DOMAIN_METHOD,
    METHOD_VERSION,
    QUERY_METHOD,
    REGISTRABLE_METHOD,
    URL_METHOD,
    compatibility,
    corroboration,
    digest,
    independence,
    normalize_domain,
    normalize_query,
    normalize_url,
    sufficiency,
)
from gis.models import (
    AnalyticalEntity,
    AnalyticalEntityType,
    AssertionStatus,
    AssetLayer,
    AssetType,
    CollectionPriorityTier,
    CollectionTarget,
    CollectionTargetEvidence,
    DataRightsPolicy,
    DemandAnalysisRun,
    DemandCoverageState,
    DemandEvidenceStrength,
    DemandObservation,
    DemandSignal,
    DemandSignalEvidence,
    EventSemanticClass,
    EvidenceCompatibility,
    EvidenceContract,
    EvidenceGap,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceQualityDimension,
    EvidenceQualityRun,
    IdentityAssertion,
    IdentityRelationship,
    PermittedUse,
    QualityDimensionState,
    QualityDimensionType,
    ResolutionStrength,
    RightsStatus,
    RightsUsability,
    SourceIndependenceState,
)
from gis.provenance.lineage import register_asset, register_lineage
from gis.provenance.service import evaluate_policy_use


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


CONTRACTS: dict[str, dict[str, Any]] = {
    "DEMAND_EMERGENCE": {"minimum_history": 4, "minimum_primary": 1, "freshness_days": 56},
    "DEMAND_ACCELERATION": {"minimum_history": 3, "minimum_primary": 1, "freshness_days": 56},
    "DEMAND_DECLINE": {"minimum_history": 4, "minimum_primary": 1, "freshness_days": 56},
    "MARKET_VISIBILITY_CHANGE": {"minimum_history": 2, "minimum_primary": 1, "freshness_days": 14},
    "COMPETITOR_PAGE_CHANGE": {"minimum_history": 1, "minimum_primary": 1, "freshness_days": 14},
    "AUTHORITY_CHANGE": {"minimum_history": 2, "minimum_primary": 1, "freshness_days": 35},
}


class EvidenceQualityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_contracts(self) -> dict[str, EvidenceContract]:
        result: dict[str, EvidenceContract] = {}
        for key, requirements in CONTRACTS.items():
            row = self.session.scalar(
                select(EvidenceContract).where(
                    EvidenceContract.contract_key == key,
                    EvidenceContract.contract_version == METHOD_VERSION,
                )
            )
            if not row:
                row = EvidenceContract(
                    contract_key=key,
                    contract_version=METHOD_VERSION,
                    description=f"Deterministic evidence requirements for {key.casefold().replace('_', ' ')}.",
                    requirements_json={
                        **requirements,
                        "required_identity": "EXACT_OR_STRONG",
                        "block_on_compatible_conflict": True,
                        "unknown_is_not_failure": True,
                    },
                )
                self.session.add(row)
                self.session.flush()
            result[key] = row
        return result

    def ensure_lineage(self) -> None:
        entity = register_asset(
            self.session, "gis_core.analytical_entity", AssetType.TABLE, AssetLayer.CORE
        )
        assertion = register_asset(
            self.session, "gis_core.identity_assertion", AssetType.EVIDENCE, AssetLayer.CORE
        )
        package = register_asset(
            self.session, "gis_core.evidence_package", AssetType.EVIDENCE, AssetLayer.CORE
        )
        planning = register_asset(
            self.session, "gis_core.collection_target_evidence", AssetType.EVIDENCE, AssetLayer.CORE
        )
        for name, layer in (
            ("gis_raw.demand_observation", AssetLayer.RAW),
            ("gis_core.demand_signal", AssetLayer.CORE),
            ("gis_core.market_definition", AssetLayer.CORE),
            ("gis_core.collection_target", AssetLayer.CORE),
            ("gis_core.data_asset_lineage", AssetLayer.CORE),
        ):
            source = register_asset(self.session, name, AssetType.TABLE, layer)
            register_lineage(self.session, source, entity, reference=METHOD_VERSION)
            register_lineage(self.session, source, package, reference=METHOD_VERSION)
        register_lineage(self.session, entity, assertion, reference=METHOD_VERSION)
        register_lineage(self.session, assertion, package, reference=METHOD_VERSION)
        register_lineage(self.session, package, planning, reference="evidence gaps only")

    def entity(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        entity_type: AnalyticalEntityType,
        value: str,
        *,
        country: str | None = None,
        language: str | None = None,
        device: str | None = None,
        source_reference_type: str | None = None,
        source_reference_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnalyticalEntity:
        details: dict[str, Any] = dict(metadata or {})
        if entity_type is AnalyticalEntityType.DOMAIN:
            domain = normalize_domain(value)
            canonical, method = domain.hostname, DOMAIN_METHOD
            details.update(registrable_domain=domain.registrable_domain, subdomain=domain.subdomain)
        elif entity_type is AnalyticalEntityType.URL:
            canonical, method = normalize_url(value), URL_METHOD
        elif entity_type is AnalyticalEntityType.QUERY:
            canonical, method = normalize_query(value), QUERY_METHOD
        else:
            canonical, method = value.strip(), "VERSIONED_REFERENCE_V1"
        identity_hash = digest(
            {
                "type": entity_type.value,
                "key": canonical,
                "country": country,
                "language": language,
                "device": device,
                "metadata": details,
            }
        )
        existing = self.session.scalar(
            select(AnalyticalEntity).where(
                AnalyticalEntity.tenant_id == tenant_id,
                AnalyticalEntity.site_id == site_id,
                AnalyticalEntity.identity_hash == identity_hash,
            )
        )
        if existing:
            return existing
        row = AnalyticalEntity(
            tenant_id=tenant_id,
            site_id=site_id,
            entity_type=entity_type,
            canonical_key=canonical,
            identity_hash=identity_hash,
            display_name=value,
            country_code=country,
            language_code=language,
            device=device,
            method_key=method,
            method_version=METHOD_VERSION,
            source_reference_type=source_reference_type,
            source_reference_id=source_reference_id,
            metadata_json=details,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def assert_identity(
        self,
        subject: AnalyticalEntity,
        object_: AnalyticalEntity,
        relationship: IdentityRelationship,
        strength: ResolutionStrength,
        method: str,
        evidence: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> IdentityAssertion:
        if subject.tenant_id != object_.tenant_id or subject.site_id != object_.site_id:
            raise ValueError("identity assertions cannot cross tenant/site scope")
        assertion_hash = digest(
            {
                "subject": str(subject.id),
                "object": str(object_.id),
                "relationship": relationship.value,
                "method": method,
                "version": METHOD_VERSION,
            }
        )
        current = self.session.scalar(
            select(IdentityAssertion).where(
                IdentityAssertion.assertion_hash == assertion_hash,
                IdentityAssertion.effective_end.is_(None),
            )
        )
        if current and current.evidence_json == evidence and current.computed_strength is strength:
            return current
        effective = now or utcnow()
        if current:
            current.effective_end = effective
            current.status = AssertionStatus.SUPERSEDED
        row = IdentityAssertion(
            subject_entity_id=subject.id,
            object_entity_id=object_.id,
            relationship=relationship,
            computed_strength=strength,
            effective_strength=strength,
            resolution_method=method,
            method_version=METHOD_VERSION,
            assertion_hash=assertion_hash,
            status=AssertionStatus.ACTIVE,
            evidence_json=evidence,
            effective_start=effective,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def resolve_domains(
        self, tenant_id: uuid.UUID, site_id: uuid.UUID, left: str, right: str
    ) -> IdentityAssertion:
        left_entity = self.entity(tenant_id, site_id, AnalyticalEntityType.DOMAIN, left)
        right_entity = self.entity(tenant_id, site_id, AnalyticalEntityType.DOMAIN, right)
        left_domain, right_domain = normalize_domain(left), normalize_domain(right)
        if left_domain.hostname == right_domain.hostname:
            relationship, strength, method = (
                IdentityRelationship.SAME_ENTITY,
                ResolutionStrength.EXACT,
                DOMAIN_METHOD,
            )
        elif left_domain.registrable_domain == right_domain.registrable_domain:
            relationship, strength, method = (
                IdentityRelationship.SAME_REGISTRABLE_DOMAIN,
                ResolutionStrength.SUPPORTED,
                REGISTRABLE_METHOD,
            )
        else:
            relationship, strength, method = (
                IdentityRelationship.RELATED_NOT_IDENTICAL,
                ResolutionStrength.UNRESOLVED,
                REGISTRABLE_METHOD,
            )
        return self.assert_identity(
            left_entity,
            right_entity,
            relationship,
            strength,
            method,
            {
                "left": left_domain.__dict__,
                "right": right_domain.__dict__,
                "same_entity_not_inferred_from_registrable_domain": True,
            },
        )

    def resolve_urls(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        left: str,
        right: str,
        relationship: IdentityRelationship,
        evidence: dict[str, Any],
    ) -> IdentityAssertion:
        left_entity = self.entity(tenant_id, site_id, AnalyticalEntityType.URL, left)
        right_entity = self.entity(tenant_id, site_id, AnalyticalEntityType.URL, right)
        if left_entity.canonical_key == right_entity.canonical_key:
            return self.assert_identity(
                left_entity,
                right_entity,
                IdentityRelationship.SAME_ENTITY,
                ResolutionStrength.EXACT,
                URL_METHOD,
                {**evidence, "normalized_url_match": True},
            )
        if relationship not in {
            IdentityRelationship.REDIRECTS_TO,
            IdentityRelationship.CANONICAL_OF,
        }:
            raise ValueError("same-resource URL resolution requires redirect or canonical evidence")
        canonical_target = evidence.get("canonical_target")
        redirect_target = evidence.get("redirect_target")
        conflicting = bool(
            canonical_target and redirect_target and canonical_target != redirect_target
        )
        return self.assert_identity(
            left_entity,
            right_entity,
            relationship,
            ResolutionStrength.CONFLICTING if conflicting else ResolutionStrength.STRONG,
            "URL_RESOLUTION_PRECEDENCE_V1",
            {
                **evidence,
                "normalized_url_match": False,
                "conflict_not_arbitrarily_resolved": conflicting,
            },
        )

    def _condition(self, signal: DemandSignal) -> str:
        return {
            "EMERGING": "DEMAND_EMERGENCE",
            "ACCELERATING": "DEMAND_ACCELERATION",
            "DECLINING": "DEMAND_DECLINE",
        }.get(signal.signal_type.value, f"DEMAND_{signal.signal_type.value}")

    def assess(
        self, tenant_id: uuid.UUID, site_id: uuid.UUID, *, as_of: datetime | None = None
    ) -> EvidenceQualityRun:
        self.ensure_lineage()
        contracts = self.ensure_contracts()
        now = as_of or utcnow()
        signals = self.session.scalars(
            select(DemandSignal)
            .join(DemandAnalysisRun)
            .where(
                DemandAnalysisRun.tenant_id == tenant_id,
                DemandAnalysisRun.site_id == site_id,
            )
        ).all()
        fingerprint = digest(
            {
                "method": METHOD_VERSION,
                "signals": sorted((str(row.id), row.identity_hash) for row in signals),
            }
        )
        existing = self.session.scalar(
            select(EvidenceQualityRun).where(
                EvidenceQualityRun.tenant_id == tenant_id,
                EvidenceQualityRun.site_id == site_id,
                EvidenceQualityRun.fingerprint == fingerprint,
            )
        )
        if existing:
            return existing
        run = EvidenceQualityRun(
            tenant_id=tenant_id,
            site_id=site_id,
            method_version=METHOD_VERSION,
            assessed_at=now,
            fingerprint=fingerprint,
            input_count=len(signals),
            package_count=0,
            metadata_json={"provider_calls": 0, "personal_identity_resolution": False},
        )
        self.session.add(run)
        self.session.flush()
        for signal in signals:
            package = self._package(run, signal, contracts, now)
            if package:
                run.package_count += 1
        self.session.flush()
        return run

    def _package(
        self,
        run: EvidenceQualityRun,
        signal: DemandSignal,
        contracts: dict[str, EvidenceContract],
        now: datetime,
    ) -> EvidencePackage | None:
        target = self.session.get(CollectionTarget, signal.collection_target_id)
        if not target:
            return None
        entity = self.entity(
            run.tenant_id,
            run.site_id,
            AnalyticalEntityType.QUERY,
            signal.entity_key,
            country=target.country_code,
            language=target.language_code,
            device=target.device,
            source_reference_type="collection_target",
            source_reference_id=target.id,
            metadata={
                "market_definition_id": str(signal.market_definition_id),
                "market_definition_version": signal.market_definition_version,
            },
        )
        condition = self._condition(signal)
        contract = contracts.get(condition) or self._fallback_contract(condition)
        evidence_links = self.session.scalars(
            select(DemandSignalEvidence).where(DemandSignalEvidence.signal_id == signal.id)
        ).all()
        observations = [
            row
            for row in (
                self.session.get(DemandObservation, link.demand_observation_id)
                for link in evidence_links
                if link.demand_observation_id
            )
            if row
        ]
        roots = [row.source_system for row in observations]
        independence_state, independent_count = independence(roots)
        rights_states = []
        for observation in observations:
            policy = self.session.get(DataRightsPolicy, observation.rights_policy_id)
            rights_states.append(
                evaluate_policy_use(self.session, policy, PermittedUse.DERIVATIVE_CREATION).status
            )
        rights = (
            RightsUsability.BLOCKED
            if RightsStatus.DENIED in rights_states
            else RightsUsability.UNKNOWN
            if RightsStatus.UNKNOWN in rights_states or not rights_states
            else RightsUsability.USABLE
        )
        requirements = contract.requirements_json
        minimum_history = int(requirements.get("minimum_history", 1))
        completeness = (
            QualityDimensionState.SUPPORTED
            if signal.observation_count >= minimum_history
            else QualityDimensionState.LIMITED
            if signal.observation_count
            else QualityDimensionState.UNKNOWN
        )
        continuity = (
            QualityDimensionState.LIMITED
            if signal.collection_regime_changed
            or signal.coverage_state is not DemandCoverageState.OBSERVED
            else QualityDimensionState.SUPPORTED
        )
        freshness_days = int(requirements.get("freshness_days", 30))
        age_days = (now.date() - signal.window_end).days
        freshness = (
            QualityDimensionState.SUPPORTED
            if age_days <= freshness_days
            else QualityDimensionState.LIMITED
        )
        conflict_count = self._conflicts(signal)
        rights_dimension = (
            QualityDimensionState.SUPPORTED
            if rights is RightsUsability.USABLE
            else QualityDimensionState.BLOCKED
            if rights is RightsUsability.BLOCKED
            else QualityDimensionState.UNKNOWN
        )
        resolution = ResolutionStrength.EXACT
        support = sufficiency(
            identity=resolution,
            completeness=completeness,
            continuity=continuity,
            rights=rights_dimension,
            conflict_count=conflict_count,
            independent_sources=independent_count,
        )
        corroboration_state = corroboration(independent_count, conflict_count, len(observations))
        limitations: list[str] = []
        if independent_count <= 1:
            limitations.append("Only one independent root source supports this claim.")
        if completeness in {QualityDimensionState.UNKNOWN, QualityDimensionState.LIMITED}:
            limitations.append("The evidence contract's minimum comparable history is not met.")
        if freshness is QualityDimensionState.LIMITED:
            limitations.append("Evidence is stale for this contract's current-state use.")
        if conflict_count:
            limitations.append("Compatible evidence contains opposing directional claims.")
        identity_hash = digest(
            {
                "run": str(run.id),
                "signal": str(signal.id),
                "contract": str(contract.id),
                "method": METHOD_VERSION,
            }
        )
        package = EvidencePackage(
            quality_run_id=run.id,
            tenant_id=run.tenant_id,
            site_id=run.site_id,
            analytical_entity_id=entity.id,
            evidence_contract_id=contract.id,
            demand_signal_id=signal.id,
            market_definition_id=signal.market_definition_id,
            market_definition_version=signal.market_definition_version,
            condition_key=condition,
            classification=signal.signal_type.value,
            period_start=signal.window_start,
            period_end=signal.window_end,
            sufficiency=support,
            identity_resolution=resolution,
            source_independence=independence_state,
            corroboration=corroboration_state,
            rights_usability=rights,
            conflict_count=conflict_count,
            independent_source_count=independent_count,
            limitations_json=limitations,
            identity_hash=identity_hash,
            method_version=METHOD_VERSION,
        )
        self.session.add(package)
        self.session.flush()
        dimension_values = {
            QualityDimensionType.IDENTITY_RESOLUTION: QualityDimensionState.STRONG,
            QualityDimensionType.FRESHNESS: freshness,
            QualityDimensionType.COMPLETENESS: completeness,
            QualityDimensionType.TEMPORAL_CONTINUITY: continuity,
            QualityDimensionType.PROVENANCE_COMPLETENESS: QualityDimensionState.SUPPORTED
            if observations
            else QualityDimensionState.UNKNOWN,
            QualityDimensionType.SOURCE_INDEPENDENCE: QualityDimensionState.SUPPORTED
            if independent_count >= 2
            else QualityDimensionState.LIMITED
            if independent_count == 1
            else QualityDimensionState.UNKNOWN,
            QualityDimensionType.CROSS_SOURCE_CORROBORATION: QualityDimensionState.SUPPORTED
            if independent_count >= 2
            else QualityDimensionState.LIMITED
            if independent_count == 1
            else QualityDimensionState.UNKNOWN,
            QualityDimensionType.CONSISTENCY: QualityDimensionState.BLOCKED
            if conflict_count
            else QualityDimensionState.SUPPORTED,
            QualityDimensionType.METHOD_COMPATIBILITY: QualityDimensionState.SUPPORTED,
            QualityDimensionType.SCOPE_COMPATIBILITY: QualityDimensionState.SUPPORTED,
            QualityDimensionType.RIGHTS_USABILITY: rights_dimension,
        }
        for dimension, state in dimension_values.items():
            self.session.add(
                EvidenceQualityDimension(
                    evidence_package_id=package.id,
                    dimension=dimension,
                    state=state,
                    method_key=f"{dimension.value}_V1",
                    method_version=METHOD_VERSION,
                    observed_value=Decimal(signal.observation_count)
                    if dimension is QualityDimensionType.COMPLETENESS
                    else None,
                    expected_value=Decimal(minimum_history)
                    if dimension is QualityDimensionType.COMPLETENESS
                    else None,
                    reasons_json=[f"Deterministic {dimension.value.casefold()} assessment."],
                )
            )
        for index, observation in enumerate(observations):
            self.session.add(
                EvidencePackageItem(
                    evidence_package_id=package.id,
                    evidence_key=str(observation.id),
                    evidence_type="DEMAND_OBSERVATION",
                    evidence_reference_id=observation.id,
                    evidence_role="PRIMARY_DEMAND_EVIDENCE",
                    root_source_key=observation.source_system,
                    independence=SourceIndependenceState.SAME_ROOT_SOURCE
                    if index
                    else independence_state,
                    method_compatibility=EvidenceCompatibility.COMPATIBLE,
                    scope_compatibility=EvidenceCompatibility.COMPATIBLE,
                    rights_usability=rights,
                    supports_claim=True,
                    metadata_json={
                        "metric": observation.source_metric,
                        "unit": observation.unit,
                        "provider_specific": True,
                    },
                )
            )
        if support in {DemandEvidenceStrength.INSUFFICIENT, DemandEvidenceStrength.LIMITED}:
            self._gap(
                package,
                target,
                "INSUFFICIENT_HISTORY"
                if signal.observation_count < minimum_history
                else "INSUFFICIENT_INDEPENDENT_EVIDENCE",
            )
        return package

    def _fallback_contract(self, key: str) -> EvidenceContract:
        row = self.session.scalar(
            select(EvidenceContract).where(
                EvidenceContract.contract_key == key,
                EvidenceContract.contract_version == METHOD_VERSION,
            )
        )
        if row:
            return row
        row = EvidenceContract(
            contract_key=key,
            contract_version=METHOD_VERSION,
            description="Conservative fallback factual-claim evidence contract.",
            requirements_json={
                "minimum_history": 2,
                "minimum_primary": 1,
                "freshness_days": 56,
                "unknown_is_not_failure": True,
            },
        )
        self.session.add(row)
        self.session.flush()
        return row

    def _conflicts(self, signal: DemandSignal) -> int:
        if signal.relative_change is None:
            return 0
        candidates = self.session.scalars(
            select(DemandSignal).where(
                DemandSignal.id != signal.id,
                DemandSignal.market_definition_id == signal.market_definition_id,
                DemandSignal.market_definition_version == signal.market_definition_version,
                DemandSignal.entity_type == signal.entity_type,
                DemandSignal.entity_key == signal.entity_key,
                DemandSignal.window_end == signal.window_end,
            )
        ).all()
        left = {
            "entity_key": signal.entity_key,
            "metric": signal.metrics_json.get("source_metric"),
            "unit": signal.metrics_json.get("unit"),
            "market_version": signal.market_definition_version,
            "country": None,
            "language": None,
            "device": None,
            "resolution_days": signal.metrics_json.get("resolution_days"),
        }
        return sum(
            1
            for row in candidates
            if row.relative_change is not None
            and compatibility(
                left,
                {
                    "entity_key": row.entity_key,
                    "metric": row.metrics_json.get("source_metric"),
                    "unit": row.metrics_json.get("unit"),
                    "market_version": row.market_definition_version,
                    "country": None,
                    "language": None,
                    "device": None,
                    "resolution_days": row.metrics_json.get("resolution_days"),
                },
            )
            is EvidenceCompatibility.COMPATIBLE
            and (row.relative_change > 0) != (signal.relative_change > 0)
        )

    def _gap(
        self, package: EvidencePackage, target: CollectionTarget, gap_type: str
    ) -> EvidenceGap:
        identity_hash = digest({"package": str(package.id), "gap": gap_type})
        existing = self.session.scalar(
            select(EvidenceGap).where(EvidenceGap.identity_hash == identity_hash)
        )
        if existing:
            return existing
        evidence_identifier = f"evidence-gap:{identity_hash}"
        planning = self.session.scalar(
            select(CollectionTargetEvidence).where(
                CollectionTargetEvidence.target_id == target.id,
                CollectionTargetEvidence.source_system == "evidence_quality",
                CollectionTargetEvidence.evidence_identifier == evidence_identifier,
            )
        )
        if not planning:
            planning = CollectionTargetEvidence(
                target_id=target.id,
                source_system="evidence_quality",
                evidence_type="EVIDENCE_GAP",
                evidence_identifier=evidence_identifier,
                evidence_at=utcnow(),
                semantic_class=EventSemanticClass.GIS_DERIVED,
                signal_name="information_gap",
                signal_value=Decimal("1"),
                metadata_json={
                    "gap_type": gap_type,
                    "collection_only": True,
                    "scheduler_mutation": False,
                },
            )
            self.session.add(planning)
            self.session.flush()
        gap = EvidenceGap(
            evidence_package_id=package.id,
            collection_target_id=target.id,
            gap_type=gap_type,
            description="Additional compatible evidence is required by the contract.",
            desired_evidence_capability="INDEPENDENT_PRIMARY_EVIDENCE",
            urgency=CollectionPriorityTier.MEDIUM,
            identity_hash=identity_hash,
            planning_evidence_id=planning.id,
            provenance_metadata={"package_id": str(package.id), "provider_call": False},
        )
        self.session.add(gap)
        self.session.flush()
        return gap

    def explain(self, package_id: uuid.UUID) -> dict[str, Any]:
        package = self.session.get(EvidencePackage, package_id)
        if not package:
            raise ValueError("evidence package not found")
        entity = self.session.get(AnalyticalEntity, package.analytical_entity_id)
        dimensions = self.session.scalars(
            select(EvidenceQualityDimension).where(
                EvidenceQualityDimension.evidence_package_id == package.id
            )
        ).all()
        gaps = self.session.scalars(
            select(EvidenceGap).where(EvidenceGap.evidence_package_id == package.id)
        ).all()
        return {
            "package_id": package.id,
            "condition": package.condition_key,
            "target": entity.canonical_key if entity else None,
            "classification": package.classification,
            "evidence_sufficiency": package.sufficiency,
            "identity_resolution": package.identity_resolution,
            "independent_sources": package.independent_source_count,
            "corroboration": package.corroboration,
            "conflict_count": package.conflict_count,
            "rights": package.rights_usability,
            "dimensions": {row.dimension.value: row.state.value for row in dimensions},
            "limitations": package.limitations_json,
            "gaps": [row.gap_type for row in gaps],
            "business_value_assessed": False,
        }
