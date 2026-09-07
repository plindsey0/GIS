# Epic 27C — Intelligence Workbench decision UX

Epic 27C exposes the existing Epic 27 governed-intelligence records as a human decision
workflow. It adds no tables, changes no VAHomeMath surface, and never treats an LLM result as
authoritative GIS data.

## Decision path

The workbench keeps every epistemic boundary visible:

1. **Authoritative evidence** — bounded evidence packages and persisted lineage.
2. **Model inference** — structured but untrusted semantic interpretation.
3. **Human opportunity decision** — accept, reject, or request more review.
4. **Model recommendation** — generated only from accepted opportunity and evidence IDs.
5. **Human selection** — permits proposal drafting; it is not intervention approval.
6. **Experiment proposal** — a pre-execution test design with metrics, guardrails and rollback.
7. **Human proposal review** — records a decision only; it creates no intervention or execution.

Opportunities, Recommendations, and Experiment proposals provide queue and detail views.
Experiments remain executed experiment records, so proposals are a separate navigation item. The
Interventions page explains when only upstream decision artifacts exist.

## Provider safety

Page loads and detail reads are database-only and make zero LLM calls. Browser generation is
explicitly labelled **Replay (free)** and directly constructs `ReplayLLMProvider`; it never reads
`LLM_PROVIDER`, never falls through to OpenAI, and reports `paid_provider_calls: 0`. The existing
`GIS_PAID_EXECUTION_DISABLED` boundary is unchanged.

Production live execution remains CLI-only and human initiated as documented in
`governed-llm-intelligence.md`. The workbench exposes no credentials, live-provider controls, tool
calling, browsing, SQL generation, model mutation, or autonomous execution.

## Operator validation

Validate the rendered lineage with these existing VAHomeMath records:

- evidence: `84445354-9583-42cb-b40e-7359deb105e1`
- opportunity: `c4023c14-ef44-43a4-9986-39b311e8f49b`
- recommendation: `96860545-d77b-410e-9e55-d8412267a06f`

Start with `scripts/dev-workbench.sh`, open `/opportunities`, and follow links without copying UUIDs
into CLI commands. Review actions require a named human actor and persist in the existing review
tables. Replay generation uses the same prompts, validation, audit, and lineage services as
production generation.

## Verification

```bash
TEST_DATABASE_URL=postgresql+psycopg://gis:gis@localhost:5433/gis_test .venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy src
cd apps/workbench
npm test
npm run lint
npm run typecheck
npm run build
```

No migration is required for Epic 27C.

The later governed-intelligence handoff follow-up enriches proposal list/detail read models with
provider, model, prompt version, creation time, typed evidence-reference count, and proposal
supersession state. `NEEDS_REVIEW` regeneration is an explicit replay-only browser operation and
preserves the original artifact and review history. Technical UUID/run payloads remain available
for audit while the parent chain and generation metadata are exposed directly.
