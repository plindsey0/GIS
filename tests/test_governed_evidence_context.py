from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_opportunities import package

from gis.intelligence.provider import ReplayLLMProvider
from gis.intelligence.schemas import EvidenceReference
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
    Opportunity,
    RightsUsability,
)


def opportunity_response(evidence_ids: list[uuid.UUID]) -> dict[str, object]:
    return {"candidate_opportunity": {"opportunities": [{
        "title": "Bounded candidate", "summary": "A bounded candidate",
        "opportunity_type": "SEO", "problem_or_signal": "A supplied signal",
        "reasoning": "Uses only governed context",
        "evidence_ids": [str(item) for item in evidence_ids],
        "expected_value": "Unknown until tested", "confidence": 0.4,
        "suggested_action": "Run a bounded test", "assumptions": [], "limitations": [],
    }]}}


def clone_package(current: EvidencePackage, **changes: object) -> EvidencePackage:
    values = {
        column.name: getattr(current, column.name)
        for column in EvidencePackage.__table__.columns
        if column.name not in {"id", "identity_hash", "created_at"}
    }
    values.update(identity_hash=uuid.uuid4().hex, **changes)
    return EvidencePackage(**values)


def test_entity_scope_discovers_bounded_siblings_and_excludes_blocked(session: Session) -> None:
    tenant, site, current = package(session, DemandEvidenceStrength.LIMITED)
    historical = clone_package(
        current, classification="STABLE", rights_usability=RightsUsability.USABLE
    )
    historical.sufficiency = DemandEvidenceStrength.SUPPORTED
    blocked = clone_package(
        current, classification="BLOCKED_TEST", rights_usability=RightsUsability.BLOCKED
    )
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
    provider = ReplayLLMProvider(opportunity_response([uuid.uuid4()]))
    with pytest.raises(IntelligenceValidationError, match="not supplied"):
        GovernedIntelligenceService(session, provider).generate_opportunities(packet)
    run = session.scalar(select(LLMRun))
    assert run
    assert run.provider_metadata_json["evidence_packet_construction_mode"] == "entity_scoped"
    assert run.provider_metadata_json["analytical_entity_id"] == str(current.analytical_entity_id)


@pytest.mark.parametrize("reference_type", [
    "EXTERNAL_SEARCH_OBSERVATION", "GSC_SEARCH_OBSERVATION",
    "GA4_EVENT_OBSERVATION", "OBSERVED_QUERY_PAGE_ASSOCIATION",
])
def test_valid_enriched_reference_is_accepted_and_maps_to_package_lineage(
    session: Session, reference_type: str
) -> None:
    tenant, site, current = package(session, DemandEvidenceStrength.SUPPORTED)
    packet = EvidencePacketService(session).build_for_entity(
        tenant.id, site.id, current.analytical_entity_id
    )
    reference_id = uuid.uuid4()
    packet.referenceable_evidence.append(EvidenceReference(
        reference_id=reference_id,
        reference_type=reference_type,
        packet_section="test_enriched_context",
        evidence_package_ids=[current.id],
    ))
    provider = ReplayLLMProvider(opportunity_response([reference_id]))

    created = GovernedIntelligenceService(session, provider).generate_opportunities(packet)

    assert len(created) == 1
    assert session.scalar(select(LLMRun)).validation_status == "VALID"  # type: ignore[union-attr]
    assert session.scalar(select(Opportunity)).id == created[0].id  # type: ignore[union-attr]
    assert provider.external is False


def test_live_failure_ids_reproduce_provider_free_and_are_valid_when_allowlisted(
    session: Session,
) -> None:
    tenant, site, current = package(session, DemandEvidenceStrength.SUPPORTED)
    packet = EvidencePacketService(session).build_for_entity(
        tenant.id, site.id, current.analytical_entity_id
    )
    rejected = {
        uuid.UUID("72489043-bc78-425f-b253-1f7cd1fed6f9"): "GSC_SEARCH_OBSERVATION",
        uuid.UUID("f0769310-f3a8-4ad7-9175-2cd1fa6c57c3"): "EXTERNAL_SEARCH_OBSERVATION",
        uuid.UUID("cf764955-4f18-4bc2-95d9-d78e35b0af6e"): "EXTERNAL_SEARCH_OBSERVATION",
        uuid.UUID("48deb4a4-db22-4a15-b8b6-da0bd9b60bc7"): "GA4_EVENT_OBSERVATION",
        uuid.UUID("b2a5e280-0411-4c1c-aeda-d8f68d0de496"): "GA4_EVENT_OBSERVATION",
        uuid.UUID("d8e736f5-a0df-45df-a819-be28f8547f9b"): "GA4_EVENT_OBSERVATION",
        uuid.UUID("cf9f70bc-8751-4b5a-8656-95411831c0ae"): "GA4_EVENT_OBSERVATION",
        uuid.UUID("f9b2c4b7-7469-489d-9187-836a6a08996e"): "GA4_EVENT_OBSERVATION",
        uuid.UUID("6dcbd2ad-3d9d-4d99-90dc-595461eb9cf3"): "GA4_EVENT_OBSERVATION",
    }
    packet.referenceable_evidence.extend(
        EvidenceReference(
            reference_id=reference_id, reference_type=reference_type,
            packet_section="reproduced_enriched_context", evidence_package_ids=[current.id],
        ) for reference_id, reference_type in rejected.items()
    )
    provider = ReplayLLMProvider(opportunity_response(list(rejected)))
    assert GovernedIntelligenceService(session, provider).generate_opportunities(packet)
    assert len(provider.calls) == 1 and provider.external is False


def test_package_reference_is_accepted_and_explicit_mode_remains_narrow(session: Session) -> None:
    tenant, site, current = package(session, DemandEvidenceStrength.SUPPORTED)
    packet = EvidencePacketService(session).build(
        tenant.id, site.id, evidence_ids=[current.id]
    )
    assert packet.referenceable_evidence_ids == {current.id}
    service = GovernedIntelligenceService(
        session, ReplayLLMProvider(opportunity_response([current.id]))
    )
    assert service.generate_opportunities(packet)


def test_same_database_id_outside_packet_is_rejected(session: Session) -> None:
    tenant, site, current = package(session, DemandEvidenceStrength.SUPPORTED)
    outside = clone_package(current, classification="OUTSIDE_PACKET")
    session.add(outside)
    session.flush()
    packet = EvidencePacketService(session).build(
        tenant.id, site.id, evidence_ids=[current.id]
    )
    with pytest.raises(IntelligenceValidationError, match="not supplied"):
        GovernedIntelligenceService(
            session, ReplayLLMProvider(opportunity_response([outside.id]))
        ).generate_opportunities(packet)


def test_reference_with_cross_packet_lineage_is_rejected(session: Session) -> None:
    tenant, site, current = package(session, DemandEvidenceStrength.SUPPORTED)
    packet = EvidencePacketService(session).build(
        tenant.id, site.id, evidence_ids=[current.id]
    )
    packet.referenceable_evidence.append(EvidenceReference(
        reference_id=uuid.uuid4(), reference_type="GSC_SEARCH_OBSERVATION",
        packet_section="search_console", evidence_package_ids=[uuid.uuid4()],
    ))
    provider = ReplayLLMProvider(
        opportunity_response([packet.referenceable_evidence[-1].reference_id])
    )
    with pytest.raises(IntelligenceValidationError, match="lineage outside the packet"):
        GovernedIntelligenceService(session, provider).generate_opportunities(packet)
