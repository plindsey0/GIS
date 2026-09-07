from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_opportunities import package

from gis.intelligence.provider import ReplayLLMProvider
from gis.intelligence.service import (
    EvidencePacketService,
    GovernedIntelligenceService,
    IntelligenceValidationError,
)
from gis.models import (
    AnalyticalEntity,
    DemandEvidenceStrength,
    EvidencePackage,
    LLMRun,
    RightsUsability,
)


def test_entity_scope_discovers_bounded_siblings_and_excludes_blocked(session: Session) -> None:
    tenant, site, current = package(session, DemandEvidenceStrength.LIMITED)
    def sibling(classification: str, rights: RightsUsability) -> EvidencePackage:
        values = {
            column.name: getattr(current, column.name)
            for column in EvidencePackage.__table__.columns
            if column.name not in {"id", "identity_hash", "created_at"}
        }
        values.update(classification=classification, rights_usability=rights,
                      identity_hash=uuid.uuid4().hex)
        return EvidencePackage(**values)

    historical = sibling("STABLE", RightsUsability.USABLE)
    historical.sufficiency = DemandEvidenceStrength.SUPPORTED
    blocked = sibling("BLOCKED_TEST", RightsUsability.BLOCKED)
    session.add_all([historical, blocked])
    session.flush()

    first = EvidencePacketService(session).build_for_entity(
        tenant.id, site.id, current.analytical_entity_id, generated_at=current.created_at
    )
    second = EvidencePacketService(session).build_for_entity(
        tenant.id, site.id, current.analytical_entity_id, generated_at=current.created_at
    )
    assert first.construction_mode == "entity_scoped"
    assert first.evidence_ids == {current.id, historical.id}
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert blocked.id not in first.evidence_ids
    assert len(first.evidence) <= 10


def test_entity_scope_rejects_cross_scope_entity(session: Session) -> None:
    tenant, site, current = package(session, DemandEvidenceStrength.SUPPORTED)
    entity = session.get_one(AnalyticalEntity, current.analytical_entity_id)
    with pytest.raises(IntelligenceValidationError, match="permitted tenant/site"):
        EvidencePacketService(session).build_for_entity(
            uuid.uuid4(), site.id, entity.id
        )


def test_entity_mode_is_audited_and_fabricated_ids_still_fail(session: Session) -> None:
    tenant, site, current = package(session, DemandEvidenceStrength.SUPPORTED)
    packet = EvidencePacketService(session).build_for_entity(
        tenant.id, site.id, current.analytical_entity_id
    )
    provider = ReplayLLMProvider({"candidate_opportunity": {"opportunities": [{
        "title": "Bounded candidate", "summary": "A bounded candidate",
        "opportunity_type": "SEO", "problem_or_signal": "A supplied signal",
        "reasoning": "Uses only governed context", "evidence_ids": [str(uuid.uuid4())],
        "expected_value": "Unknown until tested", "confidence": 0.4,
        "suggested_action": "Run a bounded test", "assumptions": [], "limitations": [],
    }]}})
    with pytest.raises(IntelligenceValidationError, match="not supplied"):
        GovernedIntelligenceService(session, provider).generate_opportunities(packet)
    run = session.scalar(select(LLMRun))
    assert run
    assert run.provider_metadata_json["evidence_packet_construction_mode"] == "entity_scoped"
    assert run.provider_metadata_json["analytical_entity_id"] == str(current.analytical_entity_id)
