from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_content_intelligence import content_scope
from test_opportunities import package

from gis.api.semantics import collection_detail
from gis.collection_planning.service import CollectionPlanningService
from gis.evidence_quality.service import EvidenceQualityService
from gis.integrations.content_intelligence.cli import parser as content_parser
from gis.integrations.content_intelligence.extraction import extract_page
from gis.integrations.content_intelligence.retrieval import RetrievalError, RetrievalResult
from gis.integrations.owned_surface.service import (
    OwnedSurfaceObservationService,
    OwnedSurfaceValidationError,
    validate_owned_url,
)
from gis.intelligence.provider import ReplayLLMProvider
from gis.intelligence.service import EvidencePacketService
from gis.market_intelligence.service import MarketIntelligenceService
from gis.models import (
    AnalyticalEntity,
    CollectionPriorityTier,
    CollectionTargetStatus,
    CollectionTargetType,
    CompetitiveContentObservation,
    DemandEvidenceStrength,
    EventSemanticClass,
    EvidenceGap,
    EvidencePackage,
    IngestionStatus,
    Intervention,
    OwnedSurfaceObservationDetail,
    RightsDecision,
    TrackedQuery,
)

NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent / "fixtures/owned_surface/va_entitlement_calculator.html"
HTML = FIXTURE.read_bytes()
URL = "https://vahomemath.test/va-entitlement-calculator/"


class FakeRetriever:
    def __init__(
        self,
        bodies: list[bytes] | None = None,
        *,
        resolved_url: str = URL,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
        truncated: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.bodies = bodies or [HTML]
        self.resolved_url = resolved_url
        self.status = status
        self.content_type = content_type
        self.truncated = truncated
        self.error = error
        self.calls = 0

    def retrieve(self, url: str) -> RetrievalResult:
        self.calls += 1
        if self.error:
            raise self.error
        body = self.bodies[min(self.calls - 1, len(self.bodies) - 1)]
        if not self.content_type.startswith(("text/html", "application/xhtml+xml")):
            raise RetrievalError("unsupported content type")
        return RetrievalResult(
            url,
            self.resolved_url,
            NOW,
            self.status,
            self.content_type,
            body,
            self.truncated,
            {"X-Robots-Tag": "index, follow"},
        )


def governed_scope(session: Session, *, rights: RightsDecision = RightsDecision.ALLOWED):
    tenant, site, base_package = package(session, DemandEvidenceStrength.SUPPORTED)
    _, connection_id = content_scope(session, rights)
    query = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="va down payment calculator",
        normalized_query="va down payment calculator",
        country_code="US",
        language_code="en",
        device="desktop",
        requested_depth=100,
    )
    session.add(query)
    session.flush()
    market = MarketIntelligenceService(session).define(
        tenant_id=tenant.id,
        site_id=site.id,
        name=f"Owned fixture {uuid.uuid4()}",
        slug=f"owned-fixture-{uuid.uuid4()}",
        tracked_query_ids=[query.id],
    )
    target = CollectionPlanningService(session).register_target(
        market,
        CollectionTargetType.URL,
        URL,
        source_system="APPROVED_OWNED_SURFACE_REQUEST",
        evidence_type="TARGET_PAGE_CONTENT_OBSERVATION",
        evidence_identifier=str(uuid.uuid4()),
        evidence_at=NOW,
        semantic_class=EventSemanticClass.GIS_DERIVED,
        signal_name="human_authorized_collection",
        signal_value=1.0,
        human_managed=True,
    )
    target.status = CollectionTargetStatus.ACTIVE
    entity = EvidenceQualityService(session).entity(
        tenant.id,
        site.id,
        session.get(AnalyticalEntity, base_package.analytical_entity_id).entity_type,
        "va down payment calculator",
        country="US",
        language="en",
        device="desktop",
        source_reference_type="tracked_query",
        source_reference_id=query.id,
    )
    gap = EvidenceGap(
        evidence_package_id=base_package.id,
        collection_target_id=target.id,
        gap_type="TARGET_PAGE_CONTENT_OBSERVATION",
        description="No governed target-page observation exists.",
        desired_evidence_capability="OWNED_PAGE_CONTENT",
        urgency=CollectionPriorityTier.HIGH,
        identity_hash=uuid.uuid4().hex,
        provenance_metadata={},
    )
    session.add(gap)
    session.flush()
    return tenant, site, connection_id, target, entity, gap


def test_owned_surface_extracts_bounded_governed_evidence_and_workbench(
    session: Session,
) -> None:
    tenant, site, connection_id, target, entity, gap = governed_scope(session)
    provider = ReplayLLMProvider({})
    service = OwnedSurfaceObservationService(session, FakeRetriever())
    run = service.collect(connection_id, site.id, target.id, entity.id)
    assert run.status is IngestionStatus.SUCCEEDED
    detail = session.scalar(select(OwnedSurfaceObservationDetail))
    assert detail and detail.change_classification == "FIRST_OBSERVATION"
    assert detail.canonical_assessment == "MATCHES_OBSERVED_URL"
    assert detail.indexability_assessment == "NO_BLOCKING_DIRECTIVE_OBSERVED"
    assert [item["label"] for item in detail.controls_json[:2]] == [
        "Loan amount", "Entitlement already used"
    ]
    assert {item["name"] for item in detail.instrumentation_json if "name" in item} == {
        "calculator_started", "calculator_completed"
    }
    assert detail.landmarks_json["main"] == 1
    assert len(detail.raw_response_fingerprint) == 64
    assert len({detail.raw_response_fingerprint, detail.normalized_content_fingerprint,
                detail.structure_fingerprint, detail.metadata_fingerprint}) == 4
    assert detail.evidence_package_id is not None and detail.reassessment_ready is True
    assert gap.resolved_at is None
    assert gap.provenance_metadata["reassessment_ready"] is True

    packet = EvidencePacketService(session).build_for_entity(
        tenant.id, site.id, entity.id
    )
    assert packet.owned_surface_observations[0]["url"] == URL
    reference = next(item for item in packet.referenceable_evidence
                     if item.reference_id == detail.observation_id)
    assert reference.reference_type == "OWNED_SURFACE_OBSERVATION"
    assert reference.evidence_package_ids == [detail.evidence_package_id]
    assert not any("raw html" in str(item).lower() for item in packet.owned_surface_observations)
    assert len(provider.calls) == 0

    workbench = collection_detail(session, target.id, tenant.id, site.id)
    rendered = workbench["owned_surface_observations"][0]
    assert rendered["title"] == "VA Entitlement Calculator Fixture"
    assert rendered["headings"][0] == {"level": 1, "text": "VA Entitlement Calculator"}
    assert rendered["structured_data_types"] == ["WebApplication"]
    assert rendered["important_internal_links"]
    assert rendered["quality_state"] == "USABLE_LIMITED"
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


def test_scope_ssrf_redirect_and_inactive_target_fail_closed(session: Session) -> None:
    _, site, connection_id, target, entity, _ = governed_scope(session)
    target.display_value = "http://127.0.0.1/admin"
    target.normalized_identity = target.display_value
    retriever = FakeRetriever()
    with pytest.raises(OwnedSurfaceValidationError, match="outside|prohibited"):
        OwnedSurfaceObservationService(session, retriever).collect(
            connection_id, site.id, target.id, entity.id
        )
    assert retriever.calls == 0

    target.display_value = "https://evil.test/page"
    with pytest.raises(OwnedSurfaceValidationError, match="outside"):
        OwnedSurfaceObservationService(session, retriever).collect(
            connection_id, site.id, target.id, entity.id
        )
    assert retriever.calls == 0

    target.display_value = URL
    target.status = CollectionTargetStatus.CANDIDATE
    with pytest.raises(OwnedSurfaceValidationError, match="active plan"):
        OwnedSurfaceObservationService(session, retriever).collect(
            connection_id, site.id, target.id, entity.id
        )
    target.status = CollectionTargetStatus.ACTIVE
    redirect = FakeRetriever(resolved_url="https://evil.test/landing")
    run = OwnedSurfaceObservationService(session, redirect).collect(
        connection_id, site.id, target.id, entity.id
    )
    assert run.status is IngestionStatus.FAILED
    assert "governed owned-site boundary" in (run.error_summary or "")
    assert session.scalar(select(func.count()).select_from(CompetitiveContentObservation)) == 0


def test_failure_partial_noindex_missing_canonical_and_rights_are_honest(
    session: Session,
) -> None:
    tenant, site, connection_id, target, entity, gap = governed_scope(session)
    failed = OwnedSurfaceObservationService(
        session, FakeRetriever(error=RetrievalError("timeout"))
    ).collect(connection_id, site.id, target.id, entity.id)
    assert failed.status is IngestionStatus.FAILED
    assert session.scalar(select(func.count()).select_from(OwnedSurfaceObservationDetail)) == 0

    partial_html = b"<html><head><meta name='robots' content='noindex'></head><body></body></html>"
    partial = OwnedSurfaceObservationService(
        session, FakeRetriever([partial_html], status=404, truncated=True)
    ).collect(connection_id, site.id, target.id, entity.id)
    assert partial.status is IngestionStatus.SUCCEEDED
    detail = session.scalar(select(OwnedSurfaceObservationDetail))
    assert detail and detail.quality_state == "PARTIAL"
    assert detail.canonical_assessment == "NOT_DECLARED"
    assert detail.indexability_assessment == "OBSERVED_NOINDEX"
    assert any("truncated" in item.lower() for item in detail.limitations_json)
    assert gap.resolved_at is None and not detail.reassessment_ready
    package_row = session.get(EvidencePackage, detail.evidence_package_id)
    assert package_row and package_row.sufficiency is DemandEvidenceStrength.LIMITED
    assert collection_detail(session, target.id, tenant.id, site.id)["owned_surface_observations"]

    server_error = OwnedSurfaceObservationService(
        session, FakeRetriever([b"<html><main><h1>Server error</h1></main>"], status=500)
    ).collect(connection_id, site.id, target.id, entity.id)
    assert server_error.status is IngestionStatus.SUCCEEDED
    server_observation = session.scalar(select(CompetitiveContentObservation).where(
        CompetitiveContentObservation.ingestion_run_id == server_error.id
    ))
    latest = session.get(
        OwnedSurfaceObservationDetail,
        server_observation.id if server_observation else None,
    )
    assert latest and latest.indexability_assessment == "HTTP_NOT_INDEXABLE"
    assert latest.reassessment_ready is False


def test_unchanged_recollection_is_audited_and_changes_preserve_history(session: Session) -> None:
    _, site, connection_id, target, entity, _ = governed_scope(session)
    changed = HTML.replace(b"How the estimate works", b"Understanding the estimate")
    retriever = FakeRetriever([HTML, HTML, changed])
    service = OwnedSurfaceObservationService(session, retriever)
    first = service.collect(connection_id, site.id, target.id, entity.id)
    unchanged = service.collect(connection_id, site.id, target.id, entity.id)
    changed_run = service.collect(connection_id, site.id, target.id, entity.id)
    assert unchanged.source_metadata["idempotent_replay"] is True
    assert unchanged.records_inserted == 0
    details = list(session.scalars(select(OwnedSurfaceObservationDetail)))
    assert len(details) == 2
    observations = list(session.scalars(select(CompetitiveContentObservation)))
    assert len(observations) == 2 and observations[0].effective_end is not None
    first_observation = next(item for item in observations if item.ingestion_run_id == first.id)
    changed_observation = next(
        item for item in observations if item.ingestion_run_id == changed_run.id
    )
    changed_detail = session.get(OwnedSurfaceObservationDetail, changed_observation.id)
    assert changed_detail
    assert changed_detail.previous_observation_id == first_observation.id
    assert "CONTENT" in changed_detail.change_classification
    assert all(run.status is IngestionStatus.SUCCEEDED for run in (first, unchanged, changed_run))


def test_url_validator_rejects_credentials_and_non_http(session: Session) -> None:
    _, site, _, _, _, _ = governed_scope(session)
    with pytest.raises((ValueError, OwnedSurfaceValidationError)):
        validate_owned_url(site, "file:///etc/passwd")
    with pytest.raises(OwnedSurfaceValidationError, match="credentials"):
        validate_owned_url(site, "https://user:secret@vahomemath.test/page")


def test_owned_command_is_explicit_and_parser_only_makes_no_network_call() -> None:
    values = [str(uuid.uuid4()) for _ in range(4)]
    args = content_parser().parse_args([
        "collect-owned-surface",
        "--connection", values[0],
        "--site", values[1],
        "--collection-target", values[2],
        "--analytical-entity", values[3],
    ])
    assert args.command == "collect-owned-surface"
    assert str(args.collection_target) == values[2]


def test_malformed_html_yields_only_deterministic_partial_facts() -> None:
    page = extract_page(
        b"<html><head><title>Broken<body><main><h1>Observed heading",
        URL,
    )
    assert "Broken" in page.visible_text
    assert page.canonical_url is None


def test_non_html_and_rights_denial_create_no_owned_observation(session: Session) -> None:
    _, site, connection_id, target, entity, _ = governed_scope(session)
    non_html = OwnedSurfaceObservationService(
        session, FakeRetriever(content_type="application/pdf")
    ).collect(connection_id, site.id, target.id, entity.id)
    assert non_html.status is IngestionStatus.FAILED
    assert session.scalar(select(func.count()).select_from(OwnedSurfaceObservationDetail)) == 0

    _, denied_site, denied_connection, denied_target, denied_entity, denied_gap = governed_scope(
        session, rights=RightsDecision.PROHIBITED
    )
    retriever = FakeRetriever()
    with pytest.raises(PermissionError, match="normalized_retention is DENIED"):
        OwnedSurfaceObservationService(session, retriever).collect(
            denied_connection, denied_site.id, denied_target.id, denied_entity.id
        )
    assert retriever.calls == 0
    assert denied_gap.provenance_metadata == {}
