from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_opportunities import package

from gis.evidence_quality.service import EvidenceQualityService
from gis.intelligence.provider import ReplayLLMProvider
from gis.intelligence.service import EvidencePacketService
from gis.models import (
    AnalyticalEntity,
    AnalyticalEntityType,
    DemandEvidenceStrength,
    Intervention,
    LLMRun,
    QueryPageIntentAssessment,
    QueryPageIntentReview,
    RightsUsability,
)
from gis.query_page_intent.service import (
    GovernedReference,
    IntentResolutionError,
    QueryPageIntentContext,
    QueryPageIntentService,
)

QUERY = "va down payment calculator"
URL = "https://www.vahomemath.test/va-entitlement-calculator/"


def setup_context(session: Session, *, page: bool = True, serp: bool = True, rights=RightsUsability.USABLE):
    tenant, site, evidence = package(session, DemandEvidenceStrength.SUPPORTED, rights=rights)
    query_entity = session.get_one(AnalyticalEntity, evidence.analytical_entity_id)
    query_entity.canonical_key = QUERY
    query_entity.display_name = QUERY
    page_entity = EvidenceQualityService(session).entity(
        tenant.id, site.id, AnalyticalEntityType.URL, URL
    )
    refs = [
        GovernedReference(
            reference_id=uuid.uuid4(), reference_type="GSC_SEARCH_OBSERVATION",
            evidence_package_ids=[evidence.id], exact_query=QUERY, page_url=URL,
            root_source="google_search_console",
        ),
        GovernedReference(
            reference_id=uuid.uuid4(), reference_type="EXTERNAL_KEYWORD_RANKING",
            evidence_package_ids=[evidence.id], exact_query=QUERY, page_url=URL,
            root_source="dataforseo", provider_declared_intent="commercial",
        ),
    ]
    if serp:
        refs.append(GovernedReference(
            reference_id=uuid.uuid4(), reference_type="SERP_RESULT",
            evidence_package_ids=[evidence.id], exact_query=QUERY, page_url=URL,
            root_source="exact_serp",
        ))
    context = QueryPageIntentContext(
        tenant_id=tenant.id, site_id=site.id, query_entity_id=query_entity.id,
        page_entity_id=page_entity.id, exact_query=QUERY, candidate_url=URL,
        references=refs,
        page_content_claims=(
            ["The title describes a VA down payment calculator.", "A calculator form is observed."]
            if page else []
        ),
        serp_claims=(["Calculator-oriented results are observed in the exact-query SERP."] if serp else []),
        page_content_fingerprint="page-v1" if page else None,
        serp_fingerprint="serp-v1" if serp else None,
        quality={"freshness": "SUPPORTED", "source_independence": "INDEPENDENT"},
    )
    return tenant, site, evidence, query_entity, page_entity, context


def response(context: QueryPageIntentContext, targeting="SUPPORTED", satisfaction="SUPPORTED"):
    return {
        "query": QUERY,
        "candidate_url": URL,
        "interpreted_user_need": "Estimate a VA-backed home purchase down payment.",
        "targeting_state": targeting,
        "intent_satisfaction_state": satisfaction,
        "supporting_evidence_ids": [str(row.reference_id) for row in context.references],
        "conflicting_evidence_ids": [],
        "page_content_claims": context.page_content_claims,
        "serp_claims": context.serp_claims,
        "reasoning_summary": "The bounded page and SERP observations support this state.",
        "assumptions": [],
        "limitations": [],
        "confidence_metadata": "Qualitative support only; not calibrated.",
        "evidence_gap_types": [],
        "suggested_next_resolution_action": "Request human review.",
    }


def service(session: Session, context: QueryPageIntentContext, **changes):
    payload = response(context, **changes)
    provider = ReplayLLMProvider({"query_page_intent_resolution": payload})
    return QueryPageIntentService(session, provider), provider, payload


def test_strong_alignment_is_versioned_governed_and_provider_free(session: Session) -> None:
    tenant, site, evidence, _, _, context = setup_context(session)
    resolver, provider, _ = service(session, context)
    assessment = resolver.resolve(context)
    assert assessment.association_state == "SUPPORTED"
    assert assessment.targeting_state == "SUPPORTED"
    assert assessment.intent_satisfaction_state == "SUPPORTED"
    assert assessment.origin == "REPLAY"
    assert len(provider.calls) == 1 and provider.external is False
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0
    run = session.get_one(LLMRun, assessment.llm_run_id)
    assert run.validation_status == "VALID"
    assert run.input_evidence_ids_json
    packet = EvidencePacketService(session).build_for_entity(
        tenant.id, site.id, context.query_entity_id
    )
    assert packet.query_page_relationships[0]["association"] == "SUPPORTED"
    reference = next(row for row in packet.referenceable_evidence if row.reference_id == assessment.id)
    assert reference.reference_type == "QUERY_PAGE_INTENT_ASSERTION"
    assert reference.evidence_package_ids == [evidence.id]


@pytest.mark.parametrize(
    ("page", "serp", "targeting", "satisfaction"),
    [
        (True, True, "PARTIAL", "PARTIAL"),
        (True, True, "NOT_SUPPORTED", "NOT_SUPPORTED"),
        (False, True, "INSUFFICIENT_EVIDENCE", "INSUFFICIENT_EVIDENCE"),
        (True, False, "UNRESOLVED", "INSUFFICIENT_EVIDENCE"),
        (True, True, "CONFLICTING_EVIDENCE", "CONFLICTING_EVIDENCE"),
    ],
)
def test_partial_unsupported_missing_and_conflicting_states(
    session: Session, page: bool, serp: bool, targeting: str, satisfaction: str
) -> None:
    *_, context = setup_context(session, page=page, serp=serp)
    resolver, _, _ = service(session, context, targeting=targeting, satisfaction=satisfaction)
    result = resolver.resolve(context)
    assert (result.targeting_state, result.intent_satisfaction_state) == (targeting, satisfaction)


def test_deterministic_association_keeps_sources_independent(session: Session) -> None:
    *_, context = setup_context(session)
    assert QueryPageIntentService.association_state(context) == "SUPPORTED"
    unrelated = context.model_copy(deep=True)
    unrelated.references = [row.model_copy(update={"page_url": None}) for row in context.references]
    assert QueryPageIntentService.association_state(unrelated) == "NOT_OBSERVED"


@pytest.mark.parametrize(
    "reference_type",
    ["GSC_SEARCH_OBSERVATION", "EXTERNAL_KEYWORD_RANKING", "SERP_RESULT"],
)
def test_each_exact_query_source_can_support_association(
    session: Session, reference_type: str
) -> None:
    *_, context = setup_context(session)
    context.references = [
        context.references[0].model_copy(
            update={"reference_type": reference_type, "root_source": reference_type.casefold()}
        )
    ]
    assert QueryPageIntentService.association_state(context) == "SUPPORTED"


@pytest.mark.parametrize("mutation", ["query", "url", "evidence", "page_claim", "serp_claim"])
def test_untrusted_output_validation_fails_closed(session: Session, mutation: str) -> None:
    *_, context = setup_context(session)
    resolver, _, payload = service(session, context)
    if mutation == "query":
        payload["query"] = "related calculator"
    elif mutation == "url":
        payload["candidate_url"] = "https://vahomemath.test/other/"
    elif mutation == "evidence":
        payload["supporting_evidence_ids"] = [str(uuid.uuid4())]
    elif mutation == "page_claim":
        payload["page_content_claims"] = ["The page converts users."]
    else:
        payload["serp_claims"] = ["A competitor has a hidden ranking advantage."]
    with pytest.raises(IntentResolutionError):
        resolver.resolve(context)
    assert session.scalar(select(func.count()).select_from(QueryPageIntentAssessment)) == 0
    run = session.scalar(select(LLMRun).where(LLMRun.task_type == "query_page_intent_resolution"))
    assert run and run.validation_status == "INVALID"


def test_scope_market_rights_and_exact_identity_fail_before_replay(session: Session) -> None:
    tenant, site, _, _, _, context = setup_context(session)
    resolver, provider, _ = service(session, context)
    for changed in (
        context.model_copy(update={"tenant_id": uuid.uuid4()}),
        context.model_copy(update={"exact_query": "related calculator"}),
        context.model_copy(update={"candidate_url": "https://vahomemath.test/other/"}),
    ):
        with pytest.raises(IntentResolutionError):
            resolver.resolve(changed)
    assert provider.calls == [] and tenant.id and site.id

    *_, blocked_context = setup_context(session, rights=RightsUsability.BLOCKED)
    blocked, blocked_provider, _ = service(session, blocked_context)
    with pytest.raises(IntentResolutionError, match="rights"):
        blocked.resolve(blocked_context)
    assert blocked_provider.calls == []


def test_history_reassessment_and_human_review_are_append_only(session: Session) -> None:
    tenant, site, _, _, _, context = setup_context(session)
    resolver, _, _ = service(session, context)
    first = resolver.resolve(context)
    resolver.mark_reassessment_needed(first.id, page_fingerprint="page-v2", serp_fingerprint="serp-v1")
    assert first.reassessment_needed and first.reassessment_reasons_json == ["PAGE_CONTENT_CHANGED"]
    changed = context.model_copy(update={"page_content_fingerprint": "page-v2"})
    second_resolver, _, _ = service(session, changed, targeting="PARTIAL", satisfaction="PARTIAL")
    second = second_resolver.resolve(changed)
    assert second.previous_assessment_id == first.id and not first.is_current and second.is_current
    second_resolver.review(second.id, tenant_id=tenant.id, site_id=site.id, decision="DISAGREE", reviewer="human", comment="Needs functional evidence")
    assert second.intent_satisfaction_state == "PARTIAL"
    assert session.scalar(select(func.count()).select_from(QueryPageIntentAssessment)) == 2
    assert session.scalar(select(func.count()).select_from(QueryPageIntentReview)) == 1
    view = second_resolver.read_model(second.id, tenant.id, site.id)
    assert view["human_review"]["current_disposition"] == "DISAGREE"
    assert view["relationship"] == {
        "association": "SUPPORTED", "targeting": "PARTIAL", "intent_satisfaction": "PARTIAL"
    }
