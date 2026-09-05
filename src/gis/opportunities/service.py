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
    EvidencePackage,
    Opportunity,
    OpportunityDetectorPolicy,
    OpportunityEvaluation,
    OpportunityEvidence,
    OpportunityFamily,
    OpportunityOverride,
    OpportunityPriority,
    OpportunityStatus,
    RightsUsability,
)
from gis.provenance.lineage import register_asset, register_lineage

VERSION = "OPPORTUNITY_DETECTOR_V2"

DETECTORS: dict[str, dict[str, Any]] = {
    "EMERGING_DEMAND_VISIBILITY_GAP": {
        "name": "Emerging demand with low owned visibility",
        "family": OpportunityFamily.DEMAND,
        "contract": "DEMAND_EMERGENCE",
        "classifications": ["EMERGING"],
        "enabled": True,
        "activation_sufficiency": ["SUPPORTED", "STRONGLY_SUPPORTED"],
        "watch_sufficiency": ["LIMITED"],
        "requires_metadata": {"owned_visibility": "LOW"},
        "materiality_components": ["demand_strength", "visibility_gap", "evidence_strength"],
        "claim_type": "LONGITUDINAL",
        "temporal_requirement": "MULTIPLE_OBSERVATIONS",
    },
    "DEMAND_ACCELERATION_GAP": {
        "name": "Accelerating demand with low owned visibility",
        "family": OpportunityFamily.DEMAND,
        "contract": "DEMAND_ACCELERATION",
        "classifications": ["ACCELERATING"],
        "enabled": True,
        "activation_sufficiency": ["SUPPORTED", "STRONGLY_SUPPORTED"],
        "watch_sufficiency": ["LIMITED"],
        "requires_metadata": {"owned_visibility": "LOW"},
        "materiality_components": [
            "demand_strength",
            "visibility_gap",
            "persistence",
            "evidence_strength",
        ],
        "claim_type": "LONGITUDINAL",
        "temporal_requirement": "MULTIPLE_OBSERVATIONS",
    },
    "HIGH_VALUE_EVIDENCE_GAP": {
        "name": "Material condition awaiting trustworthy evidence",
        "family": OpportunityFamily.INTELLIGENCE_GAP,
        "contract": "DEMAND_EMERGENCE",
        "classifications": ["EMERGING", "ACCELERATING"],
        "enabled": True,
        "activation_sufficiency": [],
        "watch_sufficiency": ["LIMITED", "INSUFFICIENT"],
        "requires_metadata": {},
        "materiality_components": ["evidence_strength", "market_relevance"],
        "claim_type": "LONGITUDINAL",
        "temporal_requirement": "MULTIPLE_OBSERVATIONS",
    },
    "COVERAGE_GAP": {
        "name": "Meaningful current demand with deterministically absent coverage",
        "family": OpportunityFamily.CONTENT,
        "contract": "DEMAND_CURRENT_STATE",
        "classifications": ["FIRST_OBSERVED", "STABLE", "EMERGING", "ACCELERATING"],
        "enabled": True,
        "activation_sufficiency": ["SUPPORTED", "STRONGLY_SUPPORTED"],
        "watch_sufficiency": ["LIMITED"],
        "requires_metadata": {"coverage_state": "NO_COVERAGE"},
        "materiality_components": ["demand_strength", "coverage_gap", "evidence_strength"],
        "claim_type": "CROSS_SECTIONAL",
        "temporal_requirement": "CURRENT_OBSERVATION",
    },
    "DEMAND_GAP": {
        "name": "Meaningful current demand not adequately captured",
        "family": OpportunityFamily.DEMAND,
        "contract": "DEMAND_CURRENT_STATE",
        "classifications": ["FIRST_OBSERVED", "STABLE", "EMERGING", "ACCELERATING"],
        "enabled": True,
        "activation_sufficiency": ["SUPPORTED", "STRONGLY_SUPPORTED"],
        "watch_sufficiency": ["LIMITED"],
        "requires_metadata": {"owned_visibility": "LOW", "coverage_state": "NO_COVERAGE"},
        "materiality_components": ["demand_strength", "visibility_gap", "coverage_gap"],
        "claim_type": "CROSS_SECTIONAL",
        "temporal_requirement": "CURRENT_OBSERVATION",
    },
    "COMPETITIVE_GAP": {
        "name": "Meaningful current demand with favorable competitive conditions",
        "family": OpportunityFamily.COMPETITIVE,
        "contract": "COMPETITIVE_CURRENT_STATE",
        "classifications": ["FIRST_OBSERVED", "STABLE", "EMERGING", "ACCELERATING"],
        "enabled": False,
        "activation_sufficiency": ["SUPPORTED", "STRONGLY_SUPPORTED"],
        "watch_sufficiency": ["LIMITED"],
        "requires_metadata": {"competition_state": "FAVORABLE", "coverage_state": "NO_COVERAGE"},
        "materiality_components": ["demand_strength", "competitive_feasibility"],
        "claim_type": "COMPOSITE",
        "temporal_requirement": "CURRENT_OBSERVATION",
    },
}


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class OpportunityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_policies(self) -> dict[str, OpportunityDetectorPolicy]:
        result: dict[str, OpportunityDetectorPolicy] = {}
        for key, spec in DETECTORS.items():
            row = self.session.scalar(
                select(OpportunityDetectorPolicy).where(
                    OpportunityDetectorPolicy.detector_key == key,
                    OpportunityDetectorPolicy.detector_version == VERSION,
                )
            )
            if not row:
                row = OpportunityDetectorPolicy(
                    detector_key=key,
                    detector_version=VERSION,
                    name=spec["name"],
                    family=spec["family"],
                    opportunity_type=key,
                    evidence_contract_key=spec["contract"],
                    enabled=spec["enabled"],
                    experimental=False,
                    policy_json={
                        k: v
                        for k, v in spec.items()
                        if k not in {"name", "family", "contract", "enabled"}
                    },
                )
                self.session.add(row)
                self.session.flush()
            result[key] = row
        return result

    def ensure_lineage(self) -> None:
        package = register_asset(
            self.session, "gis_core.evidence_package", AssetType.EVIDENCE, AssetLayer.CORE
        )
        evaluation = register_asset(
            self.session, "gis_core.opportunity_evaluation", AssetType.EVIDENCE, AssetLayer.CORE
        )
        opportunity = register_asset(
            self.session, "gis_core.opportunity", AssetType.TABLE, AssetLayer.CORE
        )
        register_lineage(self.session, package, evaluation, reference=VERSION)
        register_lineage(self.session, evaluation, opportunity, reference=VERSION)

    def detect(
        self, tenant_id: uuid.UUID, site_id: uuid.UUID, *, now: datetime | None = None
    ) -> list[Opportunity]:
        effective = now or datetime.now(timezone.utc)
        self.ensure_lineage()
        policies = self.ensure_policies()
        packages = self.session.scalars(
            select(EvidencePackage)
            .where(EvidencePackage.tenant_id == tenant_id, EvidencePackage.site_id == site_id)
            .order_by(EvidencePackage.period_end)
        ).all()
        touched: list[Opportunity] = []
        for package in packages:
            entity = self.session.get(AnalyticalEntity, package.analytical_entity_id)
            if not entity:
                continue
            for key, spec in DETECTORS.items():
                policy = policies[key]
                if not policy.enabled or package.classification not in spec["classifications"]:
                    continue
                metadata = entity.metadata_json
                if any(metadata.get(k) != v for k, v in spec["requires_metadata"].items()):
                    continue
                blockers: list[str] = []
                if package.rights_usability is not RightsUsability.USABLE:
                    blockers.append(f"RIGHTS_{package.rights_usability.value}")
                if package.conflict_count:
                    blockers.append("UNRESOLVED_CONFLICT")
                sufficiency = package.sufficiency.value
                active = sufficiency in spec["activation_sufficiency"] and not blockers
                watching = sufficiency in spec["watch_sufficiency"] or bool(blockers)
                if not active and not watching:
                    continue
                computed = OpportunityStatus.ACTIVE if active else OpportunityStatus.WATCHING
                identity = digest(
                    {
                        "tenant": tenant_id,
                        "site": site_id,
                        "market": package.market_definition_id,
                        "market_version": package.market_definition_version,
                        "type": key,
                        "entity": package.analytical_entity_id,
                        "period": [package.period_start, package.period_end],
                        "detector": VERSION,
                    }
                )
                row = self.session.scalar(
                    select(Opportunity).where(Opportunity.identity_hash == identity)
                )
                if not row:
                    label = entity.display_name
                    row = Opportunity(
                        tenant_id=tenant_id,
                        site_id=site_id,
                        analytical_entity_id=entity.id,
                        market_definition_id=package.market_definition_id,
                        market_definition_version=package.market_definition_version,
                        detector_policy_id=policy.id,
                        family=spec["family"],
                        opportunity_type=key,
                        status=computed,
                        computed_status=computed,
                        priority=OpportunityPriority.MEDIUM
                        if active
                        else OpportunityPriority.WATCH,
                        evidence_sufficiency=package.sufficiency,
                        title=f"{spec['name']}: {label}",
                        condition_description=f"Observed {package.classification.casefold().replace('_', ' ')} condition for {label} qualifies under {key} evidence policy.",
                        detected_at=effective,
                        period_start=package.period_start,
                        period_end=package.period_end,
                        identity_hash=identity,
                        materiality_json={
                            name: "SUPPORTED_BY_EVIDENCE_PACKAGE"
                            for name in spec["materiality_components"]
                        },
                        priority_components_json={
                            "evidence_strength": sufficiency,
                            "materiality": "MATERIAL" if active else "PENDING_EVIDENCE",
                        },
                        limitations_json=[*package.limitations_json, *blockers],
                    )
                    self.session.add(row)
                    self.session.flush()
                evaluation_hash = digest(
                    {
                        "opportunity": row.id,
                        "package": package.identity_hash,
                        "status": computed.value,
                        "detector": VERSION,
                    }
                )
                evaluation = self.session.scalar(
                    select(OpportunityEvaluation).where(
                        OpportunityEvaluation.evaluation_hash == evaluation_hash
                    )
                )
                if not evaluation:
                    evaluation = OpportunityEvaluation(
                        opportunity_id=row.id,
                        evaluated_at=effective,
                        computed_status=computed,
                        qualifies=active,
                        evaluation_hash=evaluation_hash,
                        reasons_json=[
                            f"classification={package.classification}",
                            f"sufficiency={sufficiency}",
                        ],
                        blockers_json=blockers,
                        metrics_json={"recommendation": None, "provider_calls": 0},
                    )
                    self.session.add(evaluation)
                    self.session.flush()
                    self.session.add(
                        OpportunityEvidence(
                            opportunity_evaluation_id=evaluation.id,
                            evidence_package_id=package.id,
                            evidence_role="QUALIFICATION_EVIDENCE",
                        )
                    )
                touched.append(row)
        return touched

    def dismiss(
        self, opportunity_id: uuid.UUID, reason: str, actor: str | None = None
    ) -> Opportunity:
        row = self.session.get(Opportunity, opportunity_id)
        if not row:
            raise ValueError("opportunity not found")
        self.session.add(
            OpportunityOverride(
                opportunity_id=row.id,
                dismissed_at=datetime.now(timezone.utc),
                dismissed_by=actor,
                reason=reason,
            )
        )
        row.status = OpportunityStatus.DISMISSED
        return row

    def restore(self, opportunity_id: uuid.UUID, actor: str | None = None) -> Opportunity:
        row = self.session.get(Opportunity, opportunity_id)
        if not row:
            raise ValueError("opportunity not found")
        override = self.session.scalar(
            select(OpportunityOverride)
            .where(
                OpportunityOverride.opportunity_id == row.id,
                OpportunityOverride.restored_at.is_(None),
            )
            .order_by(OpportunityOverride.dismissed_at.desc())
        )
        if override:
            override.restored_at = datetime.now(timezone.utc)
            override.restored_by = actor
        row.status = row.computed_status
        return row

    def list(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> list[Opportunity]:
        return list(
            self.session.scalars(
                select(Opportunity)
                .where(Opportunity.tenant_id == tenant_id, Opportunity.site_id == site_id)
                .order_by(Opportunity.detected_at.desc())
            )
        )
