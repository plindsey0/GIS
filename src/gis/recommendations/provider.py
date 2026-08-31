from __future__ import annotations

from typing import Any, Protocol


class RecommendationModelProvider(Protocol):
    key: str
    model_identifier: str
    external: bool

    def generate_structured_recommendation(self, context: dict[str, Any]) -> dict[str, Any]: ...

    def repair_structured_recommendation(
        self, context: dict[str, Any], errors: list[str]
    ) -> dict[str, Any]: ...


class FixtureRecommendationProvider:
    key = "fixture"
    model_identifier = "deterministic-fixture-v1"
    external = False

    def __init__(self, output: dict[str, Any] | None = None) -> None:
        self.output = output
        self.calls = 0

    def generate_structured_recommendation(self, context: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if self.output is not None:
            return self.output
        valid = context["applicable_intervention_types"]
        if not valid:
            return {"summary": "No valid recommendation under configured contracts.", "candidates": []}
        selected = valid[0]
        parameters: dict[str, str] = {}
        for key in selected["required_parameters"]:
            if key == "target_url":
                parameters[key] = context["entity"]["canonical_key"]
            elif key == "requested_evidence_type":
                parameters[key] = "ADDITIONAL_INDEPENDENT_EVIDENCE"
            else:
                parameters[key] = "BOUNDED_SCOPE"
        return {
            "summary": "A structured intervention may be considered under the supplied opportunity and evidence constraints.",
            "candidates": [{
                "intervention_type": selected["key"],
                "intervention_type_version": selected["version"],
                "parameters": parameters,
                "target_metric": selected["supported_metrics"][0],
                "expected_direction": "INCREASE" if "CLS" not in selected["supported_metrics"][0] else "DECREASE",
                "rationale": "The registered intervention applies to the resolved entity and would test the linked opportunity using a registered metric.",
                "assumptions": ["The proposed change may affect the registered metric; this is an AI inference, not evidence or a causal claim."],
                "limitations": list(context["limitations"]),
                "fit": "SUPPORTED_FIT",
            }],
        }

    def repair_structured_recommendation(
        self, context: dict[str, Any], errors: list[str]
    ) -> dict[str, Any]:
        del errors
        return self.generate_structured_recommendation(context)


class UnconfiguredExternalProvider:
    key = "external_unconfigured"
    model_identifier = "unconfigured"
    external = True

    def generate_structured_recommendation(self, context: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("external AI provider is not configured")

    def repair_structured_recommendation(
        self, context: dict[str, Any], errors: list[str]
    ) -> dict[str, Any]:
        raise RuntimeError("external AI provider is not configured")
