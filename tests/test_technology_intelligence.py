from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.integrations.content_intelligence.retrieval import RetrievalError, RetrievalResult
from gis.integrations.technology_intelligence import cli
from gis.integrations.technology_intelligence.cli import configure_connection
from gis.integrations.technology_intelligence.detection import detect_technologies
from gis.integrations.technology_intelligence.service import (
    TechnologyCollector,
    normalize_technology_name,
    resolve_provider_technology,
    sync_technology_registry,
    technology_changes,
)
from gis.integrations.technology_intelligence.signatures import SIGNATURE_REGISTRY_VERSION
from gis.models import (
    DataRightsPolicy,
    IngestionStatus,
    RightsDecision,
    Site,
    TechnologyAlias,
    TechnologyDetection,
    TechnologyEvidence,
    TechnologyObservation,
)
from gis.seed import seed

NOW = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
TECH_HTML = b"""<html><head><meta name="generator" content="WordPress 6.6">
<script src="https://www.googletagmanager.com/gtm.js?id=GTM-X"></script>
<script src="https://www.googletagmanager.com/gtag/js?id=G-X"></script>
<script src="https://js.hs-scripts.com/123.js"></script></head>
<body data-reactroot><img src="/wp-content/a.png"><div id="__next"></div></body></html>"""


class FakeRetriever:
    def __init__(
        self,
        bodies: list[bytes] | None = None,
        *,
        headers: list[dict[str, str]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.bodies = bodies or [TECH_HTML]
        self.headers = headers or [{"Server": "cloudflare", "CF-Ray": "fixture-ray"}]
        self.error = error
        self.calls = 0

    def retrieve(self, url: str) -> RetrievalResult:
        self.calls += 1
        if self.error:
            raise self.error
        index = min(self.calls - 1, len(self.bodies) - 1)
        return RetrievalResult(
            url,
            url,
            NOW,
            200,
            "text/html",
            self.bodies[index],
            False,
            self.headers[min(index, len(self.headers) - 1)],
        )


def technology_scope(
    session: Session, decision: RightsDecision = RightsDecision.ALLOWED
) -> tuple[Site, uuid.UUID]:
    seed(session, hostname="vahomemath.test")
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert site
    connection = configure_connection(session, "vahomemath", "vahomemath")
    policy = DataRightsPolicy(
        tenant_id=site.tenant_id,
        name=f"technology fixture {uuid.uuid4()}",
        derived_storage_allowed=decision,
    )
    session.add(policy)
    session.flush()
    connection.rights_policy_id = policy.id
    session.commit()
    return site, connection.id


def result(html: bytes = TECH_HTML, headers: dict[str, str] | None = None) -> RetrievalResult:
    return RetrievalResult(
        "https://example.com/",
        "https://example.com/",
        NOW,
        200,
        "text/html",
        html,
        False,
        headers or {"Server": "cloudflare", "CF-Ray": "fixture-ray"},
    )


def test_direct_signatures_preserve_evidence_semantics_scope_and_version() -> None:
    detections = {item.technology_slug: item for item in detect_technologies(result())}
    assert {
        "wordpress",
        "react",
        "google_analytics",
        "google_tag_manager",
        "hubspot",
        "cloudflare",
    } <= set(detections)
    assert detections["cloudflare"].semantic_class == "MEASURED"
    assert detections["wordpress"].semantic_class == "HEURISTIC"
    assert detections["cloudflare"].scope == "SITE"
    assert detections["google_tag_manager"].scope == "PAGE"
    assert all(item.evidence for item in detections.values())


def test_technology_and_alias_normalization_preserves_unknowns(session: Session) -> None:
    sync_technology_registry(session)
    ga4 = resolve_provider_technology(session, "GA4", source_key="builtwith")
    assert ga4.slug == "google_analytics"
    unknown = resolve_provider_technology(
        session,
        "Vendor Novel Product",
        source_key="builtwith",
        provider_category="Provider Custom Category",
        provider_identifier="vendor-42",
    )
    assert unknown.slug == "vendor_novel_product" and unknown.category == "Provider Custom Category"
    alias = session.scalar(
        select(TechnologyAlias).where(TechnologyAlias.provider_identifier == "vendor-42")
    )
    assert alias and alias.alias == "Vendor Novel Product"
    assert normalize_technology_name(" Google-Tag_Manager ") == "google tag manager"


def test_collection_history_idempotency_evidence_and_cost(session: Session) -> None:
    site, connection_id = technology_scope(session)
    changed = TECH_HTML.replace(b"/wp-content/a.png", b"/assets/a.png")
    retriever = FakeRetriever([TECH_HTML, TECH_HTML, changed])
    collector = TechnologyCollector(session, retriever)
    first = collector.collect(
        connection_id, site.id, "https://example.com/", observation_scope="DOMAIN"
    )
    replay = collector.collect(
        connection_id, site.id, "https://example.com/", observation_scope="DOMAIN"
    )
    revision = collector.collect(
        connection_id, site.id, "https://example.com/", observation_scope="DOMAIN"
    )
    assert all(item.status is IngestionStatus.SUCCEEDED for item in (first, replay, revision))
    assert replay.records_inserted == 0 and replay.source_metadata["idempotent_replay"] is True
    observations = session.scalars(
        select(TechnologyObservation).order_by(TechnologyObservation.created_at)
    ).all()
    assert (
        len(observations) == 2
        and observations[0].effective_end
        and observations[1].effective_end is None
    )
    assert (
        observations[1].estimated_cost == 0
        and observations[1].signature_version == SIGNATURE_REGISTRY_VERSION
    )
    assert (
        observations[1].ownership_class == "COMPETITOR"
        and observations[1].observation_scope == "DOMAIN"
    )
    assert session.scalar(select(func.count()).select_from(TechnologyDetection)) > 0
    evidence = session.scalar(select(TechnologyEvidence))
    assert evidence and evidence.signature_version == SIGNATURE_REGISTRY_VERSION
    assert evidence.evidence_hash and evidence.semantic_class in {"MEASURED", "HEURISTIC"}


@pytest.mark.parametrize("decision", [RightsDecision.UNKNOWN, RightsDecision.PROHIBITED])
def test_rights_fail_closed_before_retrieval(session: Session, decision: RightsDecision) -> None:
    site, connection_id = technology_scope(session, decision)
    retriever = FakeRetriever()
    with pytest.raises(PermissionError):
        TechnologyCollector(session, retriever).collect(
            connection_id, site.id, "https://example.com/"
        )
    assert retriever.calls == 0


def test_failed_retrieval_and_site_scope_are_safe(session: Session) -> None:
    site, connection_id = technology_scope(session)
    run = TechnologyCollector(session, FakeRetriever(error=RetrievalError("timeout"))).collect(
        connection_id, site.id, "https://example.com/"
    )
    assert run.status is IngestionStatus.FAILED and "timeout" in (run.error_summary or "")
    assert session.scalar(select(func.count()).select_from(TechnologyObservation)) == 0
    with pytest.raises(ValueError):
        TechnologyCollector(session, FakeRetriever()).collect(
            connection_id, uuid.uuid4(), "https://example.com/"
        )


def test_change_detection_never_converts_non_detection_to_removed(session: Session) -> None:
    site, connection_id = technology_scope(session)
    retriever = FakeRetriever([TECH_HTML, b"<html><body>plain</body></html>"], headers=[{}, {}])
    collector = TechnologyCollector(session, retriever)
    collector.collect(connection_id, site.id, "https://example.com/")
    collector.collect(connection_id, site.id, "https://example.com/")
    changes = technology_changes(session, site.id, "example.com")
    assert any(item["change_type"] == "ADDED" for item in changes)
    assert all(item["change_type"] != "REMOVED" for item in changes)


def test_measured_header_and_ambiguous_html_do_not_overstate_certainty() -> None:
    detections = {
        item.technology_slug: item
        for item in detect_technologies(result(b"<html>react</html>", {"Server": "nginx"}))
    }
    assert detections["nginx"].semantic_class == "MEASURED"
    assert "react" not in detections


def test_cli_json_estimate_and_dry_run_make_no_requests(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Factory:
        def __call__(self) -> Factory:
            return self

        def __enter__(self) -> Session:
            return session

        def __exit__(self, *args: object) -> None:
            return None

    assert cli.run(["estimate", "--targets", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["paid_request_performed"] is False
    site, connection_id = technology_scope(session)
    monkeypatch.setattr(cli, "session_factory", Factory())
    monkeypatch.setattr(cli, "validate_public_http_url", lambda value: value)
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
    output = json.loads(capsys.readouterr().out)
    assert output["http_request_performed"] is False and output["paid_request_performed"] is False
    assert "credential" not in json.dumps(output).casefold()
