from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_governed_intelligence import responses
from test_opportunities import package

from gis.intelligence.config import provider_from_environment
from gis.intelligence.provider import (
    LLMConfigurationError,
    OpenAILLMProvider,
    ReplayLLMProvider,
)
from gis.intelligence.schemas import OpportunityOutput
from gis.intelligence.service import (
    EvidencePacketService,
    GovernedIntelligenceService,
    IntelligenceValidationError,
)
from gis.models import DemandEvidenceStrength, LLMRun


class MockResponsesAPI:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = outputs
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            id=f"resp_mock_{len(self.calls)}",
            status="completed",
            service_tier="mock",
            output_parsed=self.outputs.pop(0),
            usage=SimpleNamespace(input_tokens=101, output_tokens=37),
        )


class MockOpenAIClient:
    def __init__(self, outputs: list[object]) -> None:
        self.responses = MockResponsesAPI(outputs)


def opportunity_payload(evidence_id: uuid.UUID) -> dict[str, object]:
    return responses(evidence_id)["candidate_opportunity"]


def test_openai_adapter_uses_native_structured_output_without_tools() -> None:
    evidence_id = uuid.uuid4()
    client = MockOpenAIClient([opportunity_payload(evidence_id)])
    provider = OpenAILLMProvider(api_key="test-not-a-real-key", model="test-model", client=client)
    result = provider.generate_structured(
        task="candidate_opportunity",
        system_prompt="system",
        user_prompt="user",
        response_schema=OpportunityOutput,
        metadata={"prompt_version": "opportunity_generation_v1"},
    )
    assert isinstance(result.value, OpportunityOutput)
    assert result.provider == "openai" and result.model == "test-model"
    assert result.input_tokens == 101 and result.output_tokens == 37 and result.cost is None
    call = client.responses.calls[0]
    assert call["text_format"] is OpportunityOutput
    assert call["tools"] == [] and call["store"] is False
    assert call["input"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]


def test_openai_configuration_fails_closed_before_client_or_network() -> None:
    with pytest.raises(LLMConfigurationError, match="human-initiated"):
        provider_from_environment(
            environment={"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "unused", "LLM_MODEL": "unused"}
        )
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY"):
        provider_from_environment(
            allow_live=True, environment={"LLM_PROVIDER": "openai", "LLM_MODEL": "test-model"}
        )
    with pytest.raises(LLMConfigurationError, match="LLM_MODEL"):
        provider_from_environment(
            allow_live=True,
            environment={"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-not-real"},
        )
    with pytest.raises(LLMConfigurationError, match="disabled"):
        provider_from_environment(
            allow_live=True,
            environment={"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "unused",
                         "LLM_MODEL": "unused", "GIS_PAID_EXECUTION_DISABLED": "1"},
        )


def test_ordinary_provider_selection_defaults_to_replay_and_never_live() -> None:
    payload = opportunity_payload(uuid.uuid4())
    provider = provider_from_environment(replay_responses={"candidate_opportunity": payload},
                                         environment={})
    assert isinstance(provider, ReplayLLMProvider)
    with pytest.raises(LLMConfigurationError, match="replay responses"):
        provider_from_environment(environment={})


def test_malformed_openai_structured_response_fails_validation() -> None:
    client = MockOpenAIClient([{"opportunities": [{"title": "missing everything else"}]}])
    provider = OpenAILLMProvider(api_key="test-not-real", model="test-model", client=client)
    with pytest.raises(ValidationError):
        provider.generate_structured(
            task="candidate_opportunity", system_prompt="system", user_prompt="user",
            response_schema=OpportunityOutput,
        )


def test_openai_fabricated_evidence_is_rejected_by_gis_validator(session: Session) -> None:
    tenant, site, evidence = package(session, DemandEvidenceStrength.SUPPORTED)
    packet = EvidencePacketService(session).build(tenant.id, site.id, evidence_ids=[evidence.id])
    invalid = opportunity_payload(uuid.uuid4())
    provider = OpenAILLMProvider(api_key="test-not-real", model="test-model",
                                 client=MockOpenAIClient([invalid]))
    with pytest.raises(IntelligenceValidationError, match="not supplied"):
        GovernedIntelligenceService(session, provider).generate_opportunities(packet)


def test_full_lineage_is_identical_through_mocked_openai_provider(session: Session) -> None:
    tenant, site, evidence = package(session, DemandEvidenceStrength.SUPPORTED)
    packet = EvidencePacketService(session).build(tenant.id, site.id, evidence_ids=[evidence.id])
    client = MockOpenAIClient([opportunity_payload(evidence.id)])
    provider = OpenAILLMProvider(api_key="test-not-real", model="test-model", client=client)
    service = GovernedIntelligenceService(session, provider)
    opportunity = service.generate_opportunities(packet)[0]
    service.review_opportunity(opportunity.id, "ACCEPTED", "human")
    client.responses.outputs.append(
        responses(evidence.id, opportunity_id=opportunity.id)["candidate_recommendation"]
    )
    recommendation = service.generate_recommendations([opportunity.id])[0]
    service.select_recommendation(recommendation.id, "human")
    client.responses.outputs.append(
        responses(evidence.id, opportunity.id, recommendation.id)["experiment_proposal"]
    )
    proposal = service.generate_experiment_proposal(recommendation.id)
    lineage = service.lineage(proposal.id)
    assert lineage["recommendation_id"] == recommendation.id
    assert lineage["opportunity_ids"] == [opportunity.id]
    assert lineage["evidence_ids"] == [evidence.id]
    assert len(client.responses.calls) == 3
    runs = list(session.scalars(select(LLMRun).order_by(LLMRun.created_at)))
    assert len(runs) == 3
    assert all(run.provider_key == "openai" and run.model_identifier == "test-model" for run in runs)
    assert all(run.input_tokens == 101 and run.output_tokens == 37 for run in runs)
    assert all(run.provider_cost is None and run.validation_status == "VALID" for run in runs)


def test_live_provider_never_reuses_a_replay_run(session: Session) -> None:
    tenant, site, evidence = package(session, DemandEvidenceStrength.SUPPORTED)
    packet = EvidencePacketService(session).build(tenant.id, site.id, evidence_ids=[evidence.id])
    replay = ReplayLLMProvider(responses(evidence.id))
    replay_opportunity = GovernedIntelligenceService(session, replay).generate_opportunities(packet)[0]
    client = MockOpenAIClient([opportunity_payload(evidence.id)])
    openai_provider = OpenAILLMProvider(
        api_key="test-not-real", model="test-model", client=client
    )
    live_opportunity = GovernedIntelligenceService(
        session, openai_provider
    ).generate_opportunities(packet)[0]
    assert len(client.responses.calls) == 1
    assert live_opportunity.id != replay_opportunity.id
