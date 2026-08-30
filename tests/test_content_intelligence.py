from __future__ import annotations

import json
import socket
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.integrations.content_intelligence import cli
from gis.integrations.content_intelligence.cli import configure_connection
from gis.integrations.content_intelligence.extraction import extract_page, normalize_url
from gis.integrations.content_intelligence.retrieval import (
    DirectHTTPRetriever,
    RetrievalError,
    RetrievalResult,
    validate_public_http_url,
)
from gis.integrations.content_intelligence.service import CompetitiveContentCollector, create_cohort
from gis.models import (
    CompetitiveContentCohortMember,
    CompetitiveContentComponent,
    CompetitiveContentDocument,
    CompetitiveContentHeading,
    CompetitiveContentObservation,
    CompetitiveContentSchemaType,
    CompetitiveContentTerm,
    DataRightsPolicy,
    IngestionStatus,
    RightsDecision,
    Site,
)
from gis.seed import seed

NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
HTML = b"""<!doctype html><html lang="en"><head><title>VA Closing Costs</title>
<meta name="description" content="A practical guide"><meta name="robots" content="index,follow">
<link rel="canonical" href="https://example.com/guide">
<script type="application/ld+json">{"@graph":[{"@type":"Article"},{"@type":"FAQPage"}]}</script>
<script type="application/ld+json">not-json</script></head><body><nav>Hidden menu words</nav>
<main><h1>VA Loan Closing Costs</h1><h2>Seller Concessions Explained</h2>
<h2>Frequently Asked Questions</h2><p>Seller concessions can affect closing costs.</p>
<table><tr><td>Comparison</td></tr></table><form><button>Apply now</button></form>
<a href="/internal" rel="nofollow">Internal details</a>
<a href="https://va.gov/reference" rel="sponsored ugc">VA source</a></main></body></html>"""


class FakeRetriever:
    def __init__(
        self, bodies: list[bytes] | None = None, *, error: Exception | None = None
    ) -> None:
        self.bodies = bodies or [HTML]
        self.error = error
        self.calls = 0

    def retrieve(self, url: str) -> RetrievalResult:
        self.calls += 1
        if self.error:
            raise self.error
        body = self.bodies[min(self.calls - 1, len(self.bodies) - 1)]
        return RetrievalResult(url, url, NOW, 200, "text/html; charset=utf-8", body, False, {})


def content_scope(
    session: Session, decision: RightsDecision = RightsDecision.ALLOWED
) -> tuple[Site, uuid.UUID]:
    seed(session, hostname="vahomemath.test")
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert site
    connection = configure_connection(session, "vahomemath", "vahomemath")
    policy = DataRightsPolicy(
        tenant_id=site.tenant_id,
        name=f"content fixture {uuid.uuid4()}",
        derived_storage_allowed=decision,
    )
    session.add(policy)
    session.flush()
    connection.rights_policy_id = policy.id
    session.commit()
    return site, connection.id


def test_deterministic_extraction_and_metric_semantics() -> None:
    page = extract_page(HTML, "https://example.com/guide?x=1")
    assert page.title == "VA Closing Costs" and page.word_count > 10
    assert page.headings[1] == (2, "Seller Concessions Explained")
    assert page.schema_types == {"Article": 1, "FAQPage": 1}
    assert [link["class"] for link in page.links] == ["INTERNAL", "EXTERNAL"]
    assert page.links[1]["rel"] == ["sponsored", "ugc"]
    components = {item["type"]: item for item in page.components}
    assert components["TABLE"]["semantics"] == "MEASURED"
    assert components["FAQ"]["semantics"] == "HEURISTIC"
    assert page.terms["seller concessions"] == 1
    assert "Hidden menu words" not in page.visible_text


def test_url_normalization_and_ssrf_protection(monkeypatch: pytest.MonkeyPatch) -> None:
    assert normalize_url("HTTPS://WWW.Example.com/path?q=1#x") == (
        "https://example.com/path?q=1",
        "example.com",
        "/path",
    )
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args: [(socket.AF_INET, 0, 0, "", ("127.0.0.1", 0))]
    )
    with pytest.raises(ValueError, match="prohibited"):
        validate_public_http_url("http://example.com/")
    with pytest.raises(ValueError):
        validate_public_http_url("file:///etc/passwd")


class FakeHTTPResponse:
    def __init__(
        self, *, status: int = 200, headers: dict[str, str] | None = None, body: bytes = HTML
    ) -> None:
        self.status_code, self.headers, self.body = (
            status,
            headers or {"Content-Type": "text/html"},
            body,
        )
        self.is_redirect = status in {301, 302, 303, 307, 308}
        self.is_permanent_redirect = status in {301, 308}

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return [self.body]


class FakeHTTPSession:
    def __init__(self, responses: list[FakeHTTPResponse]) -> None:
        self.responses = responses
        self.calls = 0

    def get(self, *args: Any, **kwargs: Any) -> FakeHTTPResponse:
        response = self.responses[self.calls]
        self.calls += 1
        return response


def test_redirect_targets_size_and_content_type_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def addresses(host: str, *args: Any) -> list[tuple[Any, ...]]:
        address = "169.254.169.254" if host == "metadata.test" else "93.184.216.34"
        return [(socket.AF_INET, 0, 0, "", (address, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", addresses)
    redirect = FakeHTTPSession(
        [FakeHTTPResponse(status=302, headers={"Location": "http://metadata.test/latest"})]
    )
    with pytest.raises(ValueError, match="prohibited"):
        DirectHTTPRetriever(session=redirect).retrieve("https://example.com")  # type: ignore[arg-type]
    oversized = FakeHTTPSession([FakeHTTPResponse(body=b"x" * 30)])
    result = DirectHTTPRetriever(session=oversized, max_bytes=10).retrieve("https://example.com")  # type: ignore[arg-type]
    assert result.truncated and len(result.body) == 10
    unsupported = FakeHTTPSession([FakeHTTPResponse(headers={"Content-Type": "application/pdf"})])
    with pytest.raises(RetrievalError, match="unsupported"):
        DirectHTTPRetriever(session=unsupported).retrieve("https://example.com")  # type: ignore[arg-type]


def test_collection_persists_features_provenance_and_revision_history(session: Session) -> None:
    site, connection_id = content_scope(session)
    changed = HTML.replace(b"Seller Concessions Explained", b"Funding Fee Explained")
    retriever = FakeRetriever([HTML, HTML, changed])
    collector = CompetitiveContentCollector(session, retriever)
    first = collector.collect(connection_id, site.id, "https://example.com/guide")
    replay = collector.collect(connection_id, site.id, "https://example.com/guide")
    revision = collector.collect(connection_id, site.id, "https://example.com/guide")
    assert all(item.status is IngestionStatus.SUCCEEDED for item in (first, replay, revision))
    assert replay.records_inserted == 0 and replay.source_metadata["idempotent_replay"] is True
    rows = session.scalars(
        select(CompetitiveContentObservation).order_by(CompetitiveContentObservation.created_at)
    ).all()
    assert len(rows) == 2 and rows[0].effective_end is not None and rows[1].effective_end is None
    assert rows[1].raw_retained is False and rows[1].render_mode == "RAW_HTTP"
    document = session.get(CompetitiveContentDocument, rows[1].id)
    assert document and document.table_count == 1 and document.internal_link_count == 1
    assert (
        session.scalar(
            select(func.count())
            .select_from(CompetitiveContentHeading)
            .where(CompetitiveContentHeading.observation_id == rows[1].id)
        )
        == 3
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(CompetitiveContentSchemaType)
            .where(CompetitiveContentSchemaType.observation_id == rows[1].id)
        )
        == 2
    )
    faq = session.scalar(
        select(CompetitiveContentComponent).where(
            CompetitiveContentComponent.component_type == "FAQ"
        )
    )
    assert faq and faq.metric_semantics == "HEURISTIC"


@pytest.mark.parametrize("decision", [RightsDecision.UNKNOWN, RightsDecision.PROHIBITED])
def test_rights_fail_closed_before_retrieval(session: Session, decision: RightsDecision) -> None:
    site, connection_id = content_scope(session, decision)
    retriever = FakeRetriever()
    with pytest.raises(PermissionError):
        CompetitiveContentCollector(session, retriever).collect(
            connection_id, site.id, "https://example.com"
        )
    assert retriever.calls == 0


def test_failed_retrieval_records_failed_run_without_zero_features(session: Session) -> None:
    site, connection_id = content_scope(session)
    run = CompetitiveContentCollector(
        session, FakeRetriever(error=RetrievalError("timeout"))
    ).collect(connection_id, site.id, "https://example.com")
    assert run.status is IngestionStatus.FAILED and "timeout" in (run.error_summary or "")
    assert session.scalar(select(func.count()).select_from(CompetitiveContentObservation)) == 0
    assert session.scalar(select(func.count()).select_from(CompetitiveContentDocument)) == 0


def test_site_isolation_and_frozen_cohort_gap_substrate(session: Session) -> None:
    site, connection_id = content_scope(session)
    owned_html = HTML.replace(b"Seller Concessions Explained", b"Funding Fee Explained")
    owned_run = CompetitiveContentCollector(session, FakeRetriever([owned_html])).collect(
        connection_id, site.id, "https://vahomemath.test/owned"
    )
    competitor_run = CompetitiveContentCollector(session, FakeRetriever()).collect(
        connection_id, site.id, "https://example.com/guide"
    )
    observations = session.scalars(select(CompetitiveContentObservation)).all()
    owned = next(item for item in observations if item.ownership_class == "OWNED")
    competitor = next(item for item in observations if item.ownership_class == "COMPETITOR")
    assert owned_run.status is competitor_run.status is IngestionStatus.SUCCEEDED
    cohort = create_cohort(
        session,
        site.id,
        "fixture cohort",
        [owned.id, competitor.id],
        rank_positions={competitor.id: 1},
    )
    members = session.scalars(
        select(CompetitiveContentCohortMember).where(
            CompetitiveContentCohortMember.cohort_id == cohort.id
        )
    ).all()
    assert len(members) == 2 and cohort.definition["immutable_membership"] is True
    competitor_terms = set(
        session.scalars(
            select(CompetitiveContentTerm.normalized_term).where(
                CompetitiveContentTerm.observation_id == competitor.id
            )
        ).all()
    )
    owned_terms = set(
        session.scalars(
            select(CompetitiveContentTerm.normalized_term).where(
                CompetitiveContentTerm.observation_id == owned.id
            )
        ).all()
    )
    assert "seller concessions" in competitor_terms - owned_terms


def test_cli_estimate_and_dry_run_are_json_and_make_no_http_calls(
    session: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Factory:
        def __call__(self) -> Factory:
            return self

        def __enter__(self) -> Session:
            return session

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(cli, "session_factory", Factory())
    site, connection_id = content_scope(session)
    monkeypatch.setattr(cli, "validate_public_http_url", lambda value: value)
    assert cli.run(["estimate", "--pages", "2"]) == 0
    estimate = json.loads(capsys.readouterr().out)
    assert estimate["estimated_cost"] == "0" and estimate["paid_request_performed"] is False
    assert (
        cli.run(
            [
                "collect",
                "--connection",
                str(connection_id),
                "--site",
                str(site.id),
                "--url",
                "https://example.com",
                "--dry-run",
            ]
        )
        == 0
    )
    dry_run = json.loads(capsys.readouterr().out)
    assert dry_run["http_request_performed"] is False
