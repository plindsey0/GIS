from __future__ import annotations

from importlib.resources import files

PROMPT_VERSIONS = {
    "candidate_opportunity": "opportunity_generation_v2",
    "candidate_recommendation": "recommendation_generation_v1",
    "experiment_proposal": "experiment_proposal_v1",
}


def system_prompt(task: str) -> str:
    version = PROMPT_VERSIONS[task]
    return files("gis.intelligence.prompt_templates").joinpath(f"{version}.txt").read_text()
