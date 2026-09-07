from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from gis.intelligence.provider import (
    LLMConfigurationError,
    LLMProvider,
    OpenAILLMProvider,
    ReplayLLMProvider,
)


def provider_from_environment(
    *,
    replay_responses: dict[str, dict[str, Any]] | None = None,
    allow_live: bool = False,
    environment: Mapping[str, str] | None = None,
    openai_client: Any | None = None,
) -> LLMProvider:
    """Select a provider explicitly; live selection requires two independent gates."""

    env = os.environ if environment is None else environment
    provider = env.get("LLM_PROVIDER", "replay").strip().casefold()
    if provider == "replay":
        if replay_responses is None:
            raise LLMConfigurationError("ReplayLLMProvider requires explicit replay responses")
        return ReplayLLMProvider(replay_responses)
    if provider != "openai":
        raise LLMConfigurationError("LLM_PROVIDER must be either replay or openai")
    if not allow_live:
        raise LLMConfigurationError(
            "Live LLM provider selection requires an explicit human-initiated command"
        )
    if env.get("GIS_PAID_EXECUTION_DISABLED") == "1":
        raise LLMConfigurationError(
            "Live LLM execution is disabled by GIS_PAID_EXECUTION_DISABLED=1"
        )
    api_key = env.get("OPENAI_API_KEY", "")
    model = env.get("LLM_MODEL", "")
    return OpenAILLMProvider(api_key=api_key, model=model, client=openai_client)
