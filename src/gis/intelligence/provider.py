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
