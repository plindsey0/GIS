from __future__ import annotations

import re
import uuid
from typing import Any


def replay_responses(
    evidence_id: uuid.UUID,
    recommendation_id: uuid.UUID | None = None,
    opportunity_id: uuid.UUID | None = None,
    target: str = "VAHomeMath",
) -> dict[str, dict[str, Any]]:
    """Deterministic, provider-free workbench/demo responses.

    This is deliberately a fixture factory rather than provider selection.  Browser
    actions which use it can never fall through to a configured live provider.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", target.casefold()).strip("-")
    target_url = f"https://vahomemath.com/{slug}/"
    result: dict[str, dict[str, Any]] = {
        "candidate_opportunity": {"opportunities": [{
            "title": f"Evaluate focused VAHomeMath coverage for {target}",
            "summary": "The supplied evidence supports evaluating a focused resource for the observed query demand.",
            "opportunity_type": "SEO", "problem_or_signal": "Observed demand and the current surface may not be fully aligned.",
            "reasoning": "The evidence packet establishes provider-reported demand for this query; it does not establish current page coverage or the effect of a content change.",
            "evidence_ids": [str(evidence_id)], "expected_value": "Potentially improve qualified discovery and engagement; magnitude unknown.",
            "confidence": 0.64, "suggested_action": "Inventory current coverage, then test one focused explanatory calculator/worksheet resource if no equivalent surface exists.",
            "assumptions": ["A current-site inventory will determine whether to update an existing page or use the proposed URL."],
            "limitations": ["The evidence contains query demand but no page-level coverage, CTR, ranking, or causal effect evidence."]}]},
    }
    if opportunity_id:
        result["candidate_recommendation"] = {"recommendations": [{
            "title": f"Test a focused resource for {target}",
            "summary": "After a same-day coverage check, publish or enhance one focused resource for the observed query.",
            "recommended_action": f"Check VAHomeMath for equivalent coverage; if absent, publish a focused worksheet/calculator guide at {target_url}; if present, apply the same treatment to that canonical page.",
            "rationale": "This uses the observed demand without asserting that a coverage gap already exists and creates a measurable, reversible content change.",
            "opportunity_ids": [str(opportunity_id)], "evidence_ids": [str(evidence_id)],
            "expected_impact": "Directional improvement in qualified organic engagement; effect size unknown.",
            "confidence": 0.67, "priority": "MEDIUM", "estimated_effort": "SMALL",
            "risks": ["A broader proposition could attract less-qualified visits."],
            "dependencies": ["Same-day current-site coverage inventory", "Ability to publish or edit the canonical page and retain baseline measurements."],
            "assumptions": ["Search and product telemetry remain available during evaluation."],
            "success_signals": ["Improved organic CTR or engagement without harming calculator completion."]}]}
    if recommendation_id:
        result["experiment_proposal"] = {
            "title": f"Focused {target} resource experiment", "recommendation_id": str(recommendation_id),
            "objective": f"Test whether focused coverage of '{target}' earns qualified organic discovery and worksheet/calculator engagement.",
            "hypothesis": "A focused, accurate worksheet/calculator guide aligned to the observed query may earn relevant impressions and engaged usage; magnitude is unknown.",
            "target_surface": f"Proposed focused resource for {target}", "target_url_or_resource": target_url,
            "control_description": "Current VAHomeMath experience before the focused treatment; first verify and record whether equivalent canonical coverage exists.",
            "treatment_description": "Publish or enhance one canonical page with a plain-language explanation of the evidenced topic, required inputs, a worked example, calculator/worksheet interaction, and links to authoritative VA guidance.",
            "implementation_steps": ["Inventory VAHomeMath for equivalent coverage and choose the existing canonical page if one exists.", "Snapshot query/page GSC metrics and current product events where available.", "Draft and fact-review the explanation, inputs, worked example, and authoritative-source links.", f"Publish the versioned treatment at {target_url} or the recorded existing canonical URL and annotate the release time."],
            "primary_metric": "Organic impressions and qualified clicks for the evidenced query/page scope",
            "secondary_metrics": ["Average organic position", "worksheet_or_calculator_started", "worksheet_or_calculator_completed"],
            "baseline_evidence_ids": [str(evidence_id)], "expected_direction": "IMPROVE",
            "expected_effect_description": "Seek directional CTR or engagement improvement; no numeric lift is assumed.",
            "evaluation_window": "Compare a documented pre-change window with at least 28 post-change days, extending for low volume or major rank volatility.",
            "minimum_observation_guidance": "Do not claim a minimum sample size from current evidence; wait for comparable query/page impressions and report uncertainty.",
            "guardrail_metrics": ["No material decline in completion rate on the canonical calculator journey"],
            "instrumentation_requirements": ["GSC query/page impressions, clicks, CTR, and position", "calculator_started and calculator_completed telemetry"],
            "dependencies": ["Current-site coverage inventory", "Fact review of VA entitlement guidance", "Stable GSC and product telemetry"],
            "risks": ["Rank changes or seasonality may confound a pre/post comparison."],
            "rollback_plan": "Restore the snapshotted title, meta description, and content block if guardrails regress or the treatment causes defects.",
            "decision_rule": "Adopt only if the primary metric improves directionally on comparable traffic and calculator completion does not materially decline; otherwise revert or mark inconclusive.",
            "implementation_notes": "Ship title/meta and content as one traceable change; record release timestamp and unrelated site/search changes."}
    return result
