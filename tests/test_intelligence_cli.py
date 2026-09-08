from __future__ import annotations

import argparse
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_governed_intelligence import responses, setup

from gis.intelligence import cli
from gis.intelligence.provider import LLMConfigurationError, ReplayLLMProvider
from gis.intelligence.service import IntelligenceValidationError
from gis.models import ExperimentProposal, Intervention, Recommendation


def proposal_args(
    recommendation_id: uuid.UUID, *, confirmed: bool = True
) -> argparse.Namespace:
    return argparse.Namespace(
        command="live-experiment-proposals",
        tenant="tenant",
        site="site",
        recommendation_id=recommendation_id,
        confirm_paid_provider_call=confirmed,
    )


def recommendation_ready_for_review(session: Session):
    tenant, site, evidence, packet, provider, service = setup(session)
    opportunity = service.generate_opportunities(packet)[0]
    service.review_opportunity(opportunity.id, "ACCEPTED", "human")
    provider.responses.update(responses(evidence.id, opportunity_id=opportunity.id))
    recommendation = service.generate_recommendations([opportunity.id])[0]
    return tenant, site, evidence, opportunity, recommendation, service


def test_live_experiment_proposals_is_registered_and_parsed() -> None:
    recommendation_id = uuid.uuid4()
    args = cli.build_parser().parse_args([
        "live-experiment-proposals",
        "--tenant", "vahomemath",
        "--site", "vahomemath",
        "--recommendation-id", str(recommendation_id),
        "--confirm-paid-provider-call",
    ])
    assert args.command == "live-experiment-proposals"
    assert args.recommendation_id == recommendation_id
    assert args.confirm_paid_provider_call is True


def test_live_experiment_proposals_requires_explicit_confirmation(session: Session) -> None:
    tenant, site, _, _, recommendation, _ = recommendation_ready_for_review(session)
    with pytest.raises(ValueError, match="requires --confirm-paid-provider-call; no call was made"):
        cli._generate_live_experiment_proposal(
            session, proposal_args(recommendation.id, confirmed=False), tenant, site
        )


def test_live_experiment_proposals_respects_paid_execution_kill_switch(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, _, _, recommendation, service = recommendation_ready_for_review(session)
    service.select_recommendation(recommendation.id, "human")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("GIS_PAID_EXECUTION_DISABLED", "1")
    with pytest.raises(LLMConfigurationError, match="disabled"):
        cli._generate_live_experiment_proposal(
            session, proposal_args(recommendation.id), tenant, site
        )


def test_live_experiment_proposals_rejects_unselected_recommendation(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, _, _, recommendation, _ = recommendation_ready_for_review(session)
    provider = ReplayLLMProvider({})
    monkeypatch.setattr(cli, "provider_from_environment", lambda **_: provider)
    with pytest.raises(IntelligenceValidationError, match="human-selected"):
        cli._generate_live_experiment_proposal(
            session, proposal_args(recommendation.id), tenant, site
        )
    assert provider.calls == []
    assert session.scalar(select(func.count()).select_from(ExperimentProposal)) == 0


def test_live_experiment_proposals_rejects_tenant_site_mismatch_before_provider(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, _, _, recommendation, _ = recommendation_ready_for_review(session)
    provider_selected = False

    def select_provider(**_: object) -> ReplayLLMProvider:
        nonlocal provider_selected
        provider_selected = True
        return ReplayLLMProvider({})

    monkeypatch.setattr(cli, "provider_from_environment", select_provider)
    wrong_tenant = SimpleNamespace(id=uuid.uuid4())
    with pytest.raises(ValueError, match="permitted tenant/site scope"):
        cli._generate_live_experiment_proposal(
            session, proposal_args(recommendation.id), wrong_tenant, site  # type: ignore[arg-type]
        )
    assert provider_selected is False
    assert tenant.id != wrong_tenant.id


def test_live_experiment_proposals_uses_governed_service_without_intervention(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, evidence, opportunity, recommendation, service = recommendation_ready_for_review(
        session
    )
    service.select_recommendation(recommendation.id, "human", "Preserve review constraint")
    provider = ReplayLLMProvider(
        responses(evidence.id, opportunity.id, recommendation.id)
    )
    monkeypatch.setattr(cli, "provider_from_environment", lambda **_: provider)

    result = cli._generate_live_experiment_proposal(
        session, proposal_args(recommendation.id), tenant, site
    )

    proposal = session.get(ExperimentProposal, uuid.UUID(result["proposal"]["id"]))  # type: ignore[index]
    assert proposal is not None
    assert result == {
        "provider": "replay",
        "model": "fixture-v1",
        "proposal": {
            "id": str(proposal.id),
            "title": proposal.title,
            "status": "READY_FOR_REVIEW",
        },
        "human_review_required": True,
        "reused_existing_artifact": False,
    }
    assert len(provider.calls) == 1
    assert provider.calls[0]["task"] == "experiment_proposal"
    assert provider.calls[0]["metadata"]["prompt_version"] == "experiment_proposal_v2"
    assert "Preserve review constraint" in provider.calls[0]["user_prompt"]
    assert session.scalar(select(func.count()).select_from(Recommendation)) == 1
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0

    no_call_provider = ReplayLLMProvider({})
    monkeypatch.setattr(cli, "provider_from_environment", lambda **_: no_call_provider)
    reused = cli._generate_live_experiment_proposal(
        session, proposal_args(recommendation.id), tenant, site
    )
    assert reused["proposal"] == result["proposal"]
    assert reused["reused_existing_artifact"] is True
    assert no_call_provider.calls == []
