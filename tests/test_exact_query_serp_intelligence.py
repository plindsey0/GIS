from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_opportunities import package

from gis.api.semantics import collection_detail
from gis.collection_planning.service import CollectionPlanningService
from gis.evidence_quality.service import EvidenceQualityService
from gis.integrations.serp.cli import parser as serp_parser
from gis.integrations.serp_intelligence.service import (
    ExactQueryScopeError,
    ExactQuerySerpService,
)
from gis.intelligence.service import EvidencePacketService
from gis.market_intelligence.service import MarketIntelligenceService
from gis.models import (
    AnalyticalEntity,
    CollectionPriorityTier,
    CollectionTargetStatus,
    CollectionTargetType,
    ConnectionType,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    DemandEvidenceStrength,
    Domain,
    EventSemanticClass,
    EvidenceGap,
    EvidencePackage,
    ExactQuerySerpSnapshotDetail,
    IngestionStatus,
    Intervention,
    RightsDecision,
    SerpObservation,
    TrackedQuery,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures/serp/exact_va_down_payment_calculator.json").read_text())


class FixtureProvider:
    def __init__(self, payloads: list[dict[str, Any]] | None = None,
                 error: Exception | None = None) -> None:
        self.payloads = payloads or [FIXTURE]
        self.error = error
        self.calls = 0

    def collect(self, query: TrackedQuery) -> dict[str, Any]:
        self.calls += 1
        if self.error:
            raise self.error
        return copy.deepcopy(self.payloads[min(self.calls - 1, len(self.payloads) - 1)])


def scope(session: Session, *, location_code: int = 2840):  # type: ignore[no-untyped-def]
    tenant, site, base_package = package(session, DemandEvidenceStrength.SUPPORTED)
    primary_domain = session.scalar(select(Domain).where(Domain.site_id == site.id))
    assert primary_domain
    primary_domain.hostname = "vahomemath.com"
    site.canonical_url = "https://www.vahomemath.com"
    source = session.scalar(select(DataSource).where(DataSource.key == "dataforseo"))
    assert source
    policy = DataRightsPolicy(
        tenant_id=tenant.id, name=f"Exact SERP fixture {uuid.uuid4()}",
        derived_storage_allowed=RightsDecision.ALLOWED,
    )
    session.add(policy)
    session.flush()
    connection = DataSourceConnection(
        tenant_id=tenant.id, site_id=site.id, data_source_id=source.id,
        rights_policy_id=policy.id,
        connection_type=ConnectionType.LICENSED_ENRICHMENT,
    )
    session.add(connection)
    query = TrackedQuery(
        tenant_id=tenant.id, site_id=site.id,
        query_text="va down payment calculator",
        normalized_query="va down payment calculator", country_code="US",
        language_code="en", device="desktop", location_code=location_code, requested_depth=100,
    )
    session.add(query)
    session.flush()
    market = MarketIntelligenceService(session).define(
        tenant_id=tenant.id, site_id=site.id, name=f"Exact SERP {uuid.uuid4()}",
        slug=f"exact-serp-{uuid.uuid4()}", tracked_query_ids=[query.id],
    )
    target = CollectionPlanningService(session).register_target(
        market, CollectionTargetType.QUERY, query.query_text,
        source_system="HUMAN_AUTHORIZED_EXACT_SERP",
        evidence_type="EXACT_QUERY_SERP_COMPETITOR_EVIDENCE",
        evidence_identifier=str(uuid.uuid4()), evidence_at=market.effective_at,
        semantic_class=EventSemanticClass.GIS_DERIVED,
        signal_name="authorized_exact_query_collection", signal_value=1,
        human_managed=True,
    )
    target.status = CollectionTargetStatus.ACTIVE
    base_entity = session.get(AnalyticalEntity, base_package.analytical_entity_id)
    assert base_entity
    entity = EvidenceQualityService(session).entity(
        tenant.id, site.id, base_entity.entity_type, query.normalized_query,
        country="US", language="en", device="desktop",
        source_reference_type="tracked_query", source_reference_id=query.id,
    )
    gap = EvidenceGap(
        evidence_package_id=base_package.id, collection_target_id=target.id,
        gap_type="EXACT_QUERY_SERP_COMPETITOR_EVIDENCE",
        description="No governed exact-query SERP snapshot exists.",
        desired_evidence_capability="exact_query_serp",
        urgency=CollectionPriorityTier.HIGH, identity_hash=uuid.uuid4().hex,
        provenance_metadata={},
    )
    session.add(gap)
    session.commit()
    return tenant, site, connection, query, market, target, entity, gap


def test_fixture_builds_governed_snapshot_packet_and_workbench(session: Session) -> None:
    tenant, site, connection, query, _, target, entity, gap = scope(session)
    provider = FixtureProvider()
    run = ExactQuerySerpService(session, provider).collect(
        connection.id, query.id, target.id, entity.id
    )
    assert run.status is IngestionStatus.SUCCEEDED and provider.calls == 1
    detail = session.scalar(select(ExactQuerySerpSnapshotDetail))
    assert detail and detail.result_count == 6 and detail.returned_depth == 25
    assert detail.owned_presence_state == "OBSERVED_WITHIN_COLLECTED_DEPTH"
    assert detail.owned_best_position == 25
    assert detail.summary_json["unique_domains"] == 3
    assert detail.summary_json["result_type_counts"]["PEOPLE_ALSO_ASK"] == 1
    assert detail.summary_json["top_results"][-1]["owned"] is True
    assert detail.reassessment_ready and gap.resolved_at is None
    assert gap.provenance_metadata["candidate_serp_observation_id"] == str(detail.observation_id)

    evidence = session.get(EvidencePackage, detail.evidence_package_id)
    assert evidence and evidence.source_independence.value == "SAME_ROOT_SOURCE"
    packet = EvidencePacketService(session).build_for_entity(tenant.id, site.id, entity.id)
    assert packet.serp_intelligence[0]["exact_query"] == query.normalized_query
    references = {item.reference_id: item for item in packet.referenceable_evidence}
    assert references[detail.observation_id].reference_type == "EXACT_QUERY_SERP_SNAPSHOT"
    result_id = uuid.UUID(packet.serp_intelligence[0]["top_results"][0]["result_id"])
    assert references[result_id].evidence_package_ids == [detail.evidence_package_id]

    view = collection_detail(session, target.id, tenant.id, site.id)
    observed = view["exact_query_serp_observations"][0]
    assert observed["exact_query"] == query.query_text
    assert observed["results"][-1]["owned_site"] is True
    assert observed["limitations"]
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [("keyword", "va entitlement calculator"), ("country_code", "CA"),
     ("language_code", "fr"), ("device", "mobile")],
)
def test_provider_scope_mismatch_fails_without_snapshot(
    session: Session, field: str, value: str
) -> None:
    _, _, connection, query, _, target, entity, _ = scope(session)
    payload = copy.deepcopy(FIXTURE)
    payload["tasks"][0]["result"][0][field] = value
    run = ExactQuerySerpService(session, FixtureProvider([payload])).collect(
        connection.id, query.id, target.id, entity.id
    )
    assert run.status is IngestionStatus.FAILED
    assert session.scalar(select(func.count()).select_from(SerpObservation)) == 0


def test_authorization_and_tenant_scope_fail_before_provider(session: Session) -> None:
    _, _, connection, query, _, target, entity, _ = scope(session)
    provider = FixtureProvider()
    target.status = CollectionTargetStatus.CANDIDATE
    with pytest.raises(ExactQueryScopeError, match="active plan"):
        ExactQuerySerpService(session, provider).collect(
            connection.id, query.id, target.id, entity.id
        )
    target.status = CollectionTargetStatus.ACTIVE
    target.display_value = "va entitlement calculator"
    with pytest.raises(ExactQueryScopeError, match="exact query"):
        ExactQuerySerpService(session, provider).collect(
            connection.id, query.id, target.id, entity.id
        )
    assert provider.calls == 0


def test_rights_denial_and_cli_registration_fail_closed(session: Session) -> None:
    _, _, connection, query, _, target, entity, _ = scope(session)
    policy = session.get(DataRightsPolicy, connection.rights_policy_id)
    assert policy
    policy.derived_storage_allowed = RightsDecision.PROHIBITED
    provider = FixtureProvider()
    with pytest.raises(PermissionError, match="DENIED"):
        ExactQuerySerpService(session, provider).collect(
            connection.id, query.id, target.id, entity.id
        )
    assert provider.calls == 0
    parsed = serp_parser().parse_args([
        "sync-exact", "--connection", str(connection.id), "--query-id", str(query.id),
        "--collection-target", str(target.id), "--analytical-entity", str(entity.id),
    ])
    assert parsed.command == "sync-exact" and parsed.collection_target == target.id


def test_duplicate_unchanged_changed_and_comparison_history(session: Session) -> None:
    _, _, connection, query, _, target, entity, _ = scope(session)
    same_later = copy.deepcopy(FIXTURE)
    same_later["tasks"][0]["id"] = "fixture-later"
    same_later["tasks"][0]["result"][0]["datetime"] = "2026-09-09T12:00:00Z"
    changed = copy.deepcopy(same_later)
    changed["tasks"][0]["id"] = "fixture-changed"
    changed["tasks"][0]["result"][0]["datetime"] = "2026-09-10T12:00:00Z"
    items = changed["tasks"][0]["result"][0]["items"]
    items[0]["rank_absolute"] = 7
    items.pop(1)
    items.append({"type": "video", "rank_absolute": 8,
                  "url": "https://video.test/watch", "title": "Video"})
    provider = FixtureProvider([FIXTURE, FIXTURE, same_later, changed])
    service = ExactQuerySerpService(session, provider)
    first = service.collect(connection.id, query.id, target.id, entity.id)
    duplicate = service.collect(connection.id, query.id, target.id, entity.id)
    unchanged = service.collect(connection.id, query.id, target.id, entity.id)
    changed_run = service.collect(connection.id, query.id, target.id, entity.id)
    assert first.status is duplicate.status is unchanged.status is changed_run.status is IngestionStatus.SUCCEEDED
    assert duplicate.source_metadata["idempotent_replay"] is True
    details = list(session.scalars(select(ExactQuerySerpSnapshotDetail).order_by(
        ExactQuerySerpSnapshotDetail.observed_at
    )))
    assert len(details) == 3
    assert details[1].change_classification == "UNCHANGED_RECOLLECTION"
    assert details[2].change_classification == "CHANGED"
    comparison = details[2].comparison_json
    assert comparison["position_movements"][0]["direction"] == "DECREASED"
    assert "VIDEO" in comparison["features_appeared"]
    assert comparison["entered_urls"] and comparison["exited_urls"]


def test_partial_malformed_duplicate_empty_absent_and_failure_are_honest(session: Session) -> None:
    _, _, connection, query, _, target, entity, gap = scope(session)
    partial = copy.deepcopy(FIXTURE)
    partial["tasks"][0]["id"] = "partial"
    items = partial["tasks"][0]["result"][0]["items"]
    items[:] = [items[1], copy.deepcopy(items[1]), {"type": "organic", "rank_absolute": 9,
        "url": "javascript:bad", "title": "Bad"}, {"type": "organic"}]
    run = ExactQuerySerpService(session, FixtureProvider([partial])).collect(
        connection.id, query.id, target.id, entity.id
    )
    assert run.status is IngestionStatus.SUCCEEDED
    detail = session.scalar(select(ExactQuerySerpSnapshotDetail))
    assert detail and detail.result_count == 1
    assert detail.owned_presence_state == "NOT_OBSERVED_WITHIN_COLLECTED_DEPTH"
    assert run.source_metadata["malformed_items"] == 2
    assert run.source_metadata["duplicate_items"] == 1
    assert gap.provenance_metadata["reassessment_ready"] is True



def test_empty_and_provider_failure_preserve_honest_state(session: Session) -> None:
    _, _, connection2, query2, _, target2, entity2, gap2 = scope(session)
    empty = copy.deepcopy(FIXTURE)
    empty["tasks"][0]["id"] = "empty"
    empty["tasks"][0]["result"] = []
    empty_run = ExactQuerySerpService(session, FixtureProvider([empty])).collect(
        connection2.id, query2.id, target2.id, entity2.id
    )
    assert empty_run.status is IngestionStatus.SUCCEEDED
    empty_observation = session.scalar(select(ExactQuerySerpSnapshotDetail).where(
        ExactQuerySerpSnapshotDetail.collection_target_id == target2.id
    ))
    assert empty_observation and empty_observation.quality_state == "INSUFFICIENT"
    assert not empty_observation.reassessment_ready and gap2.provenance_metadata == {}

    failed = ExactQuerySerpService(
        session, FixtureProvider(error=TimeoutError("fixture timeout"))
    ).collect(connection2.id, query2.id, target2.id, entity2.id)
    assert failed.status is IngestionStatus.FAILED


def test_typed_reference_registry_still_rejects_fabricated_ids(session: Session) -> None:
    tenant, site, connection, query, _, target, entity, _ = scope(session)
    ExactQuerySerpService(session, FixtureProvider()).collect(
        connection.id, query.id, target.id, entity.id
    )
    packet = EvidencePacketService(session).build_for_entity(tenant.id, site.id, entity.id)
    assert uuid.uuid4() not in packet.referenceable_evidence_ids
