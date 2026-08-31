from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.collection_planning.service import CollectionPlanningService
from gis.emerging_demand.service import EmergingDemandService
from gis.evidence_quality import cli
from gis.evidence_quality.analysis import (
    compatibility,
    corroboration,
    independence,
    normalize_domain,
    normalize_query,
    normalize_url,
)
from gis.evidence_quality.service import EvidenceQualityService
from gis.market_intelligence.service import MarketIntelligenceService
from gis.models import (
    AnalyticalEntity,
    AnalyticalEntityType,
    CollectionTargetEvidence,
    CorroborationState,
    DataRightsPolicy,
    DemandCoverageState,
    DemandEntityType,
    DemandEvidenceStrength,
    DemandObservation,
    EventSemanticClass,
    EvidenceCompatibility,
    EvidenceGap,
    EvidencePackage,
    IdentityRelationship,
    MarketDefinition,
    QualityDimensionState,
    ResolutionStrength,
    RightsDecision,
    ScheduleDefinition,
    Site,
    SourceIndependenceState,
    Tenant,
    TrackedQuery,
)
from gis.orchestration.seed import seed_vahomemath_cadence
from gis.seed import seed

NOW = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)


def test_domain_query_and_url_normalization() -> None:
    assert normalize_domain("HTTPS://WWW.Example.COM./path").hostname == "example.com"
    blog = normalize_domain("blog.example.co.uk")
    assert blog.registrable_domain == "example.co.uk"
    assert blog.subdomain == "blog"
    assert normalize_domain("münich.example").hostname == "xn--mnich-kva.example"
    assert normalize_query("  VA\u00a0Loan  CALCULATOR ") == "va loan calculator"
    assert normalize_url("HTTPS://WWW.Example.com:443/a/?utm_source=x&loan=va#top") == (
        "https://example.com/a?loan=va"
    )


def test_compatibility_independence_corroboration_and_unknown_semantics() -> None:
    base = {
        "entity_key": "q",
        "metric": "volume",
        "unit": "searches",
        "market_version": 1,
        "country": "US",
        "language": "en",
        "device": "desktop",
        "resolution_days": 28,
    }
    assert compatibility(base, dict(base)) is EvidenceCompatibility.COMPATIBLE
    assert (
        compatibility(base, {**base, "country": "GB"}) is EvidenceCompatibility.PARTIALLY_COMPATIBLE
    )
    assert (
        compatibility(base, {**base, "metric": "impressions"}) is EvidenceCompatibility.INCOMPATIBLE
    )
    assert independence(["dataforseo", "dataforseo"]) == (
        SourceIndependenceState.SAME_ROOT_SOURCE,
        1,
    )
    assert independence(["dataforseo", "gsc"])[0] is SourceIndependenceState.INDEPENDENT
    assert corroboration(1, 0, 2) is CorroborationState.SINGLE_SOURCE
    assert QualityDimensionState.UNKNOWN is not QualityDimensionState.BLOCKED
    assert QualityDimensionState.NOT_APPLICABLE is not QualityDimensionState.UNKNOWN


def scope(session: Session) -> tuple[Tenant, Site, MarketDefinition, DataRightsPolicy]:
    seed(session, hostname="vahomemath.test")
    seed_vahomemath_cadence(session)
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    query = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="evidence quality query",
        normalized_query="evidence quality query",
        country_code="US",
        language_code="en",
        device="desktop",
        requested_depth=100,
    )
    policy = DataRightsPolicy(
        tenant_id=tenant.id,
        name=f"quality-{uuid.uuid4()}",
        deterministic_analysis_allowed=RightsDecision.ALLOWED,
        derived_storage_allowed=RightsDecision.ALLOWED,
    )
    session.add_all([query, policy])
    session.flush()
    market = MarketIntelligenceService(session).define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Quality market",
        slug=f"quality-{uuid.uuid4()}",
        tracked_query_ids=[query.id],
    )
    CollectionPlanningService(session).discover(market)
    session.flush()
    return tenant, site, market, policy


def add_signal(
    session: Session,
    tenant: Tenant,
    site: Site,
    market: MarketDefinition,
    policy: DataRightsPolicy,
) -> None:
    target = CollectionPlanningService(session).discover(market)[0]
    observation = DemandObservation(
        tenant_id=tenant.id,
        site_id=site.id,
        market_definition_id=market.id,
        market_definition_version=market.version,
        collection_target_id=target.id,
        entity_type=DemandEntityType.QUERY,
        entity_key=target.normalized_identity,
        observed_date=NOW.date(),
        observed_at=NOW,
        source_system="dataforseo",
        source_metric="PROVIDER_SEARCH_VOLUME",
        value=Decimal(10),
        unit="provider_searches",
        resolution_days=28,
        country_code="US",
        language_code="en",
        device="desktop",
        semantic_class=EventSemanticClass.PROVIDER_REPORTED,
        coverage_state=DemandCoverageState.OBSERVED,
        method_key="PROVIDER_VOLUME",
        method_version="1",
        rights_policy_id=policy.id,
        observation_key=uuid.uuid4().hex,
        content_hash=uuid.uuid4().hex,
        provenance_metadata={"root_source": "dataforseo"},
        effective_start=NOW,
    )
    session.add(observation)
    session.flush()
    EmergingDemandService(session).analyze(tenant.id, site.id, market.id, analyzed_at=NOW)
    session.flush()


def test_resolution_explainability_history_and_tenant_isolation(session: Session) -> None:
    tenant, site, _, _ = scope(session)
    service = EvidenceQualityService(session)
    exact = service.resolve_domains(tenant.id, site.id, "www.example.com", "example.com")
    assert exact.relationship is IdentityRelationship.SAME_ENTITY
    assert exact.computed_strength is ResolutionStrength.EXACT
    related = service.resolve_domains(tenant.id, site.id, "blog.example.com", "example.com")
    assert related.relationship is IdentityRelationship.SAME_REGISTRABLE_DOMAIN
    assert related.evidence_json["same_entity_not_inferred_from_registrable_domain"] is True
    subject = session.get(AnalyticalEntity, related.subject_entity_id)
    object_ = session.get(AnalyticalEntity, related.object_entity_id)
    assert subject and object_
    revised = service.assert_identity(
        subject,
        object_,
        related.relationship,
        ResolutionStrength.STRONG,
        related.resolution_method,
        {"new_redirect_evidence": True},
        now=NOW,
    )
    assert revised.id != related.id and related.effective_end == NOW
    original_tenant = object_.tenant_id
    object_.tenant_id = uuid.uuid4()
    with pytest.raises(ValueError):
        service.assert_identity(
            subject,
            object_,
            IdentityRelationship.SAME_ENTITY,
            ResolutionStrength.EXACT,
            "TEST",
            {},
        )
    object_.tenant_id = original_tenant
    redirect = service.resolve_urls(
        tenant.id,
        site.id,
        "https://example.com/old",
        "https://example.com/new",
        IdentityRelationship.REDIRECTS_TO,
        {"redirect_target": "https://example.com/new"},
    )
    assert redirect.effective_strength is ResolutionStrength.STRONG
    conflict = service.resolve_urls(
        tenant.id,
        site.id,
        "https://example.com/a",
        "https://example.com/b",
        IdentityRelationship.CANONICAL_OF,
        {"canonical_target": "https://example.com/b", "redirect_target": "https://example.com/c"},
    )
    assert conflict.effective_strength is ResolutionStrength.CONFLICTING


def test_market_version_identity_and_sparse_assessment(session: Session) -> None:
    tenant, site, market, _ = scope(session)
    service = EvidenceQualityService(session)
    first = service.entity(
        tenant.id,
        site.id,
        AnalyticalEntityType.MARKET,
        market.slug,
        metadata={"market_definition_id": str(market.id), "version": 1},
    )
    second = service.entity(
        tenant.id,
        site.id,
        AnalyticalEntityType.MARKET,
        market.slug,
        metadata={"market_definition_id": str(market.id), "version": 2},
    )
    assert first.id != second.id
    run = service.assess(tenant.id, site.id, as_of=NOW)
    assert run.input_count == 0 and run.package_count == 0


def test_evidence_package_contract_gap_feedback_and_idempotency(session: Session) -> None:
    tenant, site, market, policy = scope(session)
    add_signal(session, tenant, site, market, policy)
    schedule_count = session.scalar(select(func.count()).select_from(ScheduleDefinition))
    service = EvidenceQualityService(session)
    first = service.assess(tenant.id, site.id, as_of=NOW)
    second = service.assess(tenant.id, site.id, as_of=NOW)
    assert first.id == second.id and first.package_count == 1
    package = session.scalar(
        select(EvidencePackage).where(EvidencePackage.quality_run_id == first.id)
    )
    assert package and package.sufficiency is DemandEvidenceStrength.LIMITED
    assert package.independent_source_count == 1
    assert package.source_independence is SourceIndependenceState.SAME_ROOT_SOURCE
    assert session.scalar(select(func.count()).select_from(EvidenceGap)) == 1
    assert (
        session.scalar(
            select(func.count())
            .select_from(CollectionTargetEvidence)
            .where(CollectionTargetEvidence.source_system == "evidence_quality")
        )
        == 1
    )
    explanation = service.explain(package.id)
    assert explanation["business_value_assessed"] is False
    assert "Only one independent root source supports this claim." in explanation["limitations"]
    assert session.scalar(select(func.count()).select_from(ScheduleDefinition)) == schedule_count


def test_cli_json_serialization() -> None:
    payload = {
        "id": uuid.uuid4(),
        "at": NOW,
        "amount": Decimal("1.25"),
        "state": ResolutionStrength.EXACT,
    }
    encoded = json.dumps(payload, default=cli.json_default)
    assert "EXACT" in encoded and "1.25" in encoded
