from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.competitive_events.service import SynthesisService
from gis.integrations.authority_intelligence import cli
from gis.integrations.authority_intelligence.analysis import (
    canonical_url,
    classify_anchor,
    hhi,
    net_change,
    normalize_domain,
)
from gis.integrations.authority_intelligence.provider import (
    AuthorityCollection,
    AuthorityMetric,
    AuthorityRequest,
    BacklinkRecord,
)
from gis.integrations.authority_intelligence.service import AuthorityCollector
from gis.models import (
    AnchorClassification,
    AuthorityLinkState,
    AuthorityMetricObservation,
    AuthorityObservation,
    AuthorityTargetType,
    BacklinkObservation,
    CompetitiveEvent,
    CompetitiveEventDomain,
    CompetitiveEventType,
    ConnectionStatus,
    ConnectionType,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    EventSemanticClass,
    IngestionStatus,
    ReferringDomainObservation,
    RightsDecision,
    Site,
    Tenant,
)
from gis.seed import seed

NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)


class FakeProvider:
    def __init__(self, collections: list[AuthorityCollection]) -> None:
        self.collections = collections
        self.calls = 0

    def collect(self, request: AuthorityRequest) -> AuthorityCollection:
        request.validate()
        item = self.collections[min(self.calls, len(self.collections) - 1)]
        self.calls += 1
        return item


def collection(
    *,
    observed_at: datetime = NOW,
    state: AuthorityLinkState = AuthorityLinkState.OBSERVED_NEW,
    metric_value: str = "42",
    include_link: bool = True,
) -> AuthorityCollection:
    links = (
        (
            BacklinkRecord(
                "https://News.Example/story?x=1#fragment",
                "https://VAHomeMath.test/calculator#top",
                state,
                "provider-link-1",
                "VA loan calculator",
                ("nofollow", "sponsored"),
                "TEXT",
                NOW - timedelta(days=3),
                NOW,
            ),
        )
        if include_link
        else ()
    )
    return AuthorityCollection(
        "fixture-provider",
        observed_at,
        "task-1",
        (
            AuthorityMetric(
                "domain_rating",
                "Domain Rating",
                Decimal(metric_value),
                EventSemanticClass.PROVIDER_REPORTED,
                "fixture-provider",
                Decimal("0"),
                Decimal("100"),
                methodology_version="2026-01",
            ),
        ),
        links,
        completeness="PARTIAL",
        cost=Decimal("0.01"),
    )


def scope(
    session: Session, decision: RightsDecision = RightsDecision.ALLOWED
) -> tuple[Tenant, Site, DataSourceConnection]:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    source = session.scalar(select(DataSource).where(DataSource.key == "dataforseo"))
    assert tenant and site and source
    policy = DataRightsPolicy(
        tenant_id=tenant.id,
        name=f"authority fixture {uuid.uuid4()}",
        commercial_use_allowed=decision,
        derived_storage_allowed=decision,
        raw_storage_allowed=RightsDecision.UNKNOWN,
    )
    session.add(policy)
    session.flush()
    connection = DataSourceConnection(
        tenant_id=tenant.id,
        site_id=site.id,
        data_source_id=source.id,
        rights_policy_id=policy.id,
        connection_type=ConnectionType.LICENSED_ENRICHMENT,
        status=ConnectionStatus.ACTIVE,
        configuration_json={"authority_provider": "fixture"},
        credential_reference="secret-manager://authority-fixture",
    )
    session.add(connection)
    session.commit()
    return tenant, site, connection


def test_normalization_anchor_and_derived_math() -> None:
    assert normalize_domain("HTTPS://WWW.Example.COM/path") == "example.com"
    assert canonical_url("https://WWW.Example.com/a?x=1#fragment") == (
        "https://example.com/a?x=1",
        "example.com",
    )
    anchor, confidence = classify_anchor(
        "https://example.com", "example.com", "https://example.com/a"
    )
    assert anchor is AnchorClassification.URL and confidence == 1
    assert hhi([5, 5]) == Decimal("0.50")
    assert net_change(8, 3) == 5


def test_collection_preserves_metrics_provenance_cost_history_and_anchor_rights(
    session: Session,
) -> None:
    _, site, connection = scope(session)
    provider = FakeProvider([collection(), collection(), collection(metric_value="50")])
    collector = AuthorityCollector(session, provider)
    first = collector.collect(
        connection.id,
        site.id,
        AuthorityRequest(AuthorityTargetType.DOMAIN, "vahomemath.test"),
        estimated_cost=Decimal("0.02"),
    )
    replay = collector.collect(
        connection.id,
        site.id,
        AuthorityRequest(AuthorityTargetType.DOMAIN, "vahomemath.test"),
        estimated_cost=Decimal("0.02"),
    )
    revision = collector.collect(
        connection.id,
        site.id,
        AuthorityRequest(AuthorityTargetType.DOMAIN, "vahomemath.test"),
        estimated_cost=Decimal("0.02"),
    )
    assert all(item.status is IngestionStatus.SUCCEEDED for item in (first, replay, revision))
    assert replay.records_inserted == 0 and replay.source_metadata["idempotent_replay"] is True
    observations = session.scalars(
        select(AuthorityObservation).order_by(AuthorityObservation.created_at)
    ).all()
    assert (
        len(observations) == 2
        and observations[0].effective_end
        and observations[1].effective_end is None
    )
    assert observations[1].provider_reported_cost == Decimal("0.01")
    metric = session.scalar(
        select(AuthorityMetricObservation).where(
            AuthorityMetricObservation.authority_observation_id == observations[1].id
        )
    )
    assert (
        metric
        and metric.metric_provider == "fixture-provider"
        and metric.metric_key == "domain_rating"
        and metric.metric_value == 50
    )
    link = session.scalar(
        select(BacklinkObservation).where(
            BacklinkObservation.authority_observation_id == observations[1].id
        )
    )
    assert (
        link
        and link.anchor_text is None
        and link.anchor_hash
        and link.source_domain == "news.example"
    )
    assert link.sponsored is True and link.follow_state.value == "NOFOLLOW"
    referring = session.scalar(
        select(ReferringDomainObservation).where(
            ReferringDomainObservation.authority_observation_id == observations[1].id
        )
    )
    assert (
        referring
        and referring.backlink_count == 1
        and referring.semantic_class is EventSemanticClass.GIS_DERIVED
    )


@pytest.mark.parametrize("decision", [RightsDecision.UNKNOWN, RightsDecision.PROHIBITED])
def test_rights_fail_closed_before_provider_call(
    session: Session, decision: RightsDecision
) -> None:
    _, site, connection = scope(session, decision)
    provider = FakeProvider([collection()])
    with pytest.raises(PermissionError):
        AuthorityCollector(session, provider).collect(
            connection.id, site.id, AuthorityRequest(AuthorityTargetType.DOMAIN, "vahomemath.test")
        )
    assert provider.calls == 0


def test_raw_anchor_requires_explicit_raw_retention(session: Session) -> None:
    _, site, connection = scope(session)
    provider = FakeProvider([collection()])
    with pytest.raises(PermissionError):
        AuthorityCollector(session, provider).collect(
            connection.id,
            site.id,
            AuthorityRequest(AuthorityTargetType.DOMAIN, "vahomemath.test", retain_raw_anchor=True),
        )
    assert provider.calls == 0


def test_bounds_cost_estimate_and_json_serialization(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ValueError):
        AuthorityRequest(AuthorityTargetType.DOMAIN, "example.com", row_limit=10001).validate()
    assert (
        cli.run(
            ["estimate", "--targets", "2", "--rows", "100", "--pages", "2", "--unit-cost", "0.05"]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["estimated_cost"] == "0.10" and output["paid_request_performed"] is False
    assert cli.json_default(Decimal("1.2")) == "1.2"


def test_explicit_authority_events_and_no_false_loss_from_absence(session: Session) -> None:
    tenant, site, connection = scope(session)
    provider = FakeProvider(
        [
            collection(observed_at=NOW, state=AuthorityLinkState.OBSERVED_NEW),
            collection(observed_at=NOW + timedelta(days=1), metric_value="44", include_link=False),
            collection(
                observed_at=NOW + timedelta(days=2),
                state=AuthorityLinkState.OBSERVED_LOST,
                metric_value="47",
            ),
        ]
    )
    collector = AuthorityCollector(session, provider)
    request = AuthorityRequest(AuthorityTargetType.DOMAIN, "vahomemath.test")
    collector.collect(connection.id, site.id, request)
    collector.collect(connection.id, site.id, request)
    collector.collect(connection.id, site.id, request)
    result = SynthesisService(session).synthesize(
        tenant.id,
        site.id,
        [CompetitiveEventDomain.AUTHORITY],
        NOW - timedelta(hours=1),
        NOW + timedelta(days=3),
    )
    session.commit()
    assert result["provider_cost"] == "0"
    types = set(
        session.scalars(
            select(CompetitiveEvent.event_type).where(
                CompetitiveEvent.event_domain == CompetitiveEventDomain.AUTHORITY
            )
        ).all()
    )
    assert CompetitiveEventType.BACKLINK_FIRST_OBSERVED in types
    assert CompetitiveEventType.BACKLINK_LOST in types
    assert CompetitiveEventType.AUTHORITY_METRIC_INCREASED in types
    assert list(types).count(CompetitiveEventType.BACKLINK_LOST) <= 1
    # The incomplete middle snapshot emitted no loss; only the explicit provider LOST state did.
    lost_events = session.scalars(
        select(CompetitiveEvent).where(
            CompetitiveEvent.event_type == CompetitiveEventType.BACKLINK_LOST
        )
    ).all()
    assert len(lost_events) == 1 and lost_events[0].event_time == NOW + timedelta(days=2)


def test_tenant_site_isolation(session: Session) -> None:
    _, site, connection = scope(session)
    with pytest.raises(ValueError):
        AuthorityCollector(session, FakeProvider([collection()])).collect(
            connection.id, uuid.uuid4(), AuthorityRequest(AuthorityTargetType.DOMAIN, "example.com")
        )
    assert session.scalar(select(func.count()).select_from(AuthorityObservation)) == 0
