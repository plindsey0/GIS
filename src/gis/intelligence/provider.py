from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

StructuredT = TypeVar("StructuredT", bound=BaseModel)


@dataclass(frozen=True)
class LLMResult:
    value: BaseModel
    provider: str
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None


class LLMProvider(Protocol):
    key: str
    model_identifier: str
    external: bool

    def generate_structured(
        self,
        *,
        task: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[StructuredT],
        metadata: dict[str, Any] | None = None,
    ) -> LLMResult: ...


class ReplayLLMProvider:
    """Deterministic, offline provider used by tests and provider-free demonstrations."""

    key = "replay"
    model_identifier = "fixture-v1"
    external = False

    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def generate_structured(
        self,
        *,
        task: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[StructuredT],
        metadata: dict[str, Any] | None = None,
    ) -> LLMResult:
        self.calls.append(
            {"task": task, "system_prompt": system_prompt, "user_prompt": user_prompt,
             "metadata": metadata or {}}
        )
        if task not in self.responses:
            raise ValueError(f"No replay response configured for task {task}")
        value = response_schema.model_validate(self.responses[task])
        return LLMResult(value=value, provider=self.key, model=self.model_identifier,
                         metadata={"replay": True}, cost=0)


class OpenAILLMProvider:
    """Production structured-output adapter; construction alone performs no I/O."""

    key = "openai"
    external = True

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        if not api_key.strip():
            raise LLMConfigurationError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        if not model.strip():
            raise LLMConfigurationError("LLM_MODEL is required when LLM_PROVIDER=openai")
        self.model_identifier = model
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - packaging/configuration failure
                raise LLMConfigurationError(
                    "The openai package is required for LLM_PROVIDER=openai"
                ) from exc
            client = OpenAI(api_key=api_key)
        self._client = client

    def generate_structured(
        self,
        *,
        task: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[StructuredT],
        metadata: dict[str, Any] | None = None,
    ) -> LLMResult:
        response = self._client.responses.parse(
            model=self.model_identifier,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=response_schema,
            tools=[],
            store=False,
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            status = getattr(response, "status", "unknown")
            raise ValueError(f"OpenAI returned no structured output (status={status})")
        value = response_schema.model_validate(parsed)
        usage = getattr(response, "usage", None)
        response_metadata = {
            "response_id": getattr(response, "id", None),
            "status": getattr(response, "status", None),
            "service_tier": getattr(response, "service_tier", None),
            "request_metadata": metadata or {},
            "stored_by_provider": False,
            "tools_enabled": False,
        }
        return LLMResult(
            value=value,
            provider=self.key,
            model=self.model_identifier,
            metadata=response_metadata,
            input_tokens=getattr(usage, "input_tokens", None) if usage else None,
            output_tokens=getattr(usage, "output_tokens", None) if usage else None,
            cost=None,
        )


class LLMConfigurationError(ValueError):
    """Raised before any provider call when live-provider configuration is unsafe."""
