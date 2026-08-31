# AI Recommendation Engine

Epic 8 adds a governed reasoning layer between evidence-supported opportunities and Epic 9A intervention proposals. Recommendations are advisory records, not observations, approvals, schedules, or executions.

## Trust and authority boundaries

The engine reads curated Epic 26.5 evidence packages linked through an Epic 7 opportunity. Deterministic GIS services remain authoritative for identity, evidence sufficiency, conflicts, rights, applicable intervention types, parameters, metrics, feasibility, measurement readiness, lifecycle, and approval.

```mermaid
flowchart LR
  E[Evidence package] --> O[Opportunity]
  O --> R[Recommendation run]
  R --> C[Validated candidates]
  C --> H[Human recommendation review]
  H -->|accepted candidate| I[Draft intervention]
  I --> A[Separate human approval]
  A --> X[Execution and measurement]
```

The model receives a bounded structured context, never database access or tools. Provider text is untrusted data, prompt instructions in source content are ignored, and chain-of-thought is neither requested nor stored. Persisted rationale is a concise user-facing explanation.

## Eligibility and rights

The default `RECOMMENDATION_POLICY_V1` permits active opportunities with supported or strongly supported, conflict-free, usable evidence. Watching opportunities are limited to the intelligence-gap family. An intelligence gap may only propose `EXPAND_COLLECTION`.

Rights checks fail closed. The local fixture provider does not transmit data. External providers are deliberately unconfigured and blocked before invocation because explicit AI-inference rights and data-minimization configuration have not been established. AI inference rights and model-training rights are distinct; this epic grants neither by inference.

## Structured generation

`RECOMMENDATION_PROMPT_V1` requires JSON-only candidates selected from the supplied intervention registry. Validation rejects unknown intervention types, contract versions, metrics, missing parameters, fabricated magnitude, probability, ROI, or more than three candidates. One repair attempt is allowed; invalid output and errors remain auditable. A valid empty candidate list is a supported result.

Runs record policy, provider/model identifiers, prompt version, configuration, context hash, timestamps, optional token/cost fields, validation failures, and repair count. The context hash provides idempotency; `--force` explicitly creates a new generation context.

No production provider or secret is configured. The deterministic fixture is the only operational provider in Epic 8 and makes no network or paid calls.

## Review and intervention safety

Human review supports accept, partial accept, reject, and regeneration-request semantics. Accepted candidates are converted through the existing `InterventionService`, including typed parameters, metric registry, hypothesis, and measurement contract. The resulting intervention is always `DRAFT`. Recommendation acceptance never supplies an approval actor and cannot create `APPROVED`, `SCHEDULED`, or execution states.

## CLI

```bash
gis-recommendations generate --opportunity-id UUID --dry-run
gis-recommendations generate --opportunity-id UUID
gis-recommendations generate-all --tenant-id UUID --site-id UUID --dry-run
gis-recommendations list --tenant-id UUID --site-id UUID
gis-recommendations inspect --recommendation-id UUID
gis-recommendations review --recommendation-id UUID --decision ACCEPT --reviewer NAME --candidate-id UUID
```

Dry-run reports eligibility, blockers, applicable contracts, provider/model, whether a call would occur, and known fixture cost without calling the provider or persisting a run. `generate-all` makes zero calls when no opportunities exist.

## Operations and analytics

The `ai_recommendations` pipeline is registered with daily cadence after evidence quality, opportunity detection, and intervention measurement. Its VAHomeMath schedule is seeded `DISABLED`, like all seeded schedules; this epic activates nothing.

dbt exposes run, recommendation, candidate, review, acceptance, rejection, blocker, cost, and model-performance marts. The dashboard labels recommendations as candidates for human review and does not imply execution. The capability is implemented, but remains no-data/configured until governed recommendation records exist.

## Local validation

```bash
docker compose up -d db
python -m pip install -e '.[dev]'
alembic upgrade head
gis-seed
gis-orchestrator seed-vahomemath --confirm-disabled
pytest -q tests/test_recommendations.py
cd analytics && dbt build --profiles-dir .
```

Use a disposable `TEST_DATABASE_URL` for tests. No API key is required. Production-provider enablement is future work and must add explicit rights, budget, privacy, secret-management, and operator controls before any external call.
