# Governed LLM intelligence v1

The human-facing workflow over these records is documented in
[`epic-27c-intelligence-workbench.md`](epic-27c-intelligence-workbench.md). Its browser generation
actions are replay-only and cannot select a live provider.

Epic 27 adds the provider-independent, human-governed path from authoritative GIS evidence to
an implementable experiment proposal:

```text
deterministic evidence and provenance
  -> LLM semantic proposal
  -> deterministic schema, ID, scope, lineage, and lifecycle validation
  -> human review
```

Model output is untrusted and is never authoritative merely because it is structured. GIS only
persists an artifact after Pydantic schema validation and deterministic reference/scope checks.
For entity-scoped packets, `referenceable_evidence` is the typed, packet-derived citation
allow-list. Each enriched observation maps back to governing evidence-package lineage; arbitrary
database UUIDs remain invalid. Explicit packets expose only their selected package IDs.
Evidence text is clearly labeled untrusted data in every prompt; instructions embedded in
collected content cannot change governance or lifecycle state. Confidence is model reasoning
metadata, not a calibrated probability.

## Architecture and lineage

`EvidencePacketService` supports two governed construction modes. Explicit mode selects at most
50 authoritative `evidence_package` records by explicit
tenant/site, IDs, condition, dates, and latest-N filters. It exposes stable IDs, entity context,
period, package items, source keys, rights state, quality-run provenance, and limitations. The
model never receives database access. Entity-scoped mode starts from one tenant/site/entity,
selects the latest rights-usable package per classification (maximum ten), and constructs compact,
bounded exact-match context from existing demand, ranking, GSC, GA4, market, quality, and gaps.
Related queries remain excluded without a governed relationship. Query/page association requires
an exact-query observation and a URL on the governed site; it never asserts intent satisfaction.

`LLMProvider.generate_structured` is the narrow provider boundary. `ReplayLLMProvider` returns
validated fixtures without network access or credentials. `OpenAILLMProvider` is the single
production adapter and uses the OpenAI Responses API native Pydantic structured-output parser;
it enables no tools and asks the provider not to store the response. The three versioned prompts are
`opportunity_generation_v2`, `recommendation_generation_v1`, and `experiment_proposal_v1`.
`llm_run` records provider/model, prompt version, input IDs, validated response snapshot,
validation outcome/errors, request fingerprint, and optional token/cost metadata. It never stores
hidden chain-of-thought.

Normalized links make the lineage traversable:

```text
experiment_proposal
  -> recommendation
  -> recommendation_opportunity
  -> opportunity_evaluation / opportunity_evidence
  -> evidence_package / evidence_package_item
  -> quality run, source keys, and method version
```

## Human gates

- LLM opportunities begin as `WATCHING` semantic candidates. Only the latest explicit
  `opportunity_review=ACCEPTED` decision permits recommendation generation.
- Recommendations begin `READY_FOR_REVIEW`. An explicit human selection writes the existing
  `recommendation_review` record and changes status to `ACCEPTED`.
- Experiment proposals begin `READY_FOR_REVIEW`; only a human can mark them `APPROVED`,
  `REJECTED`, or `NEEDS_REVIEW`.

The replay provider cannot self-approve any artifact. No experiment is executed and VAHomeMath
is not modified.

## Offline/free operator workflow

`ReplayLLMProvider` is the default. It is used by tests and the local demonstration, requires no
credential, makes no network request, and cannot be silently replaced by a live provider.

Set the normal, non-test `DATABASE_URL` for the local GIS database, then inspect a bounded packet:

```bash
gis-intelligence packet --tenant vahomemath --site vahomemath --limit 10
```

To constrain it to known evidence, repeat `--evidence-id UUID`. Run the complete local replay
demonstration with an explicit human actor:

```bash
gis-intelligence demo --tenant vahomemath --site vahomemath \
  --evidence-id UUID --reviewer your-name
```

The entity-scoped packet can be inspected without writing records or contacting a provider:

```bash
gis-intelligence packet --tenant vahomemath --site vahomemath \
  --entity-id 947737ce-fa06-49d5-8aef-b31fb914a828
```

The command prints the evidence packet, candidate opportunity, recorded human acceptance,
recommendation, recorded human selection, implementable experiment proposal, and complete
lineage. The provider fixture makes zero network and paid-provider calls. Invoking `demo` is the
operator's explicit request to record the two displayed human decisions; proposal approval remains
a separate future human decision.

## Live/human-initiated OpenAI workflow

A live request requires all of the following simultaneously:

- `LLM_PROVIDER=openai`;
- a non-empty `OPENAI_API_KEY`;
- a non-empty `LLM_MODEL` that the account is authorized to use;
- `GIS_PAID_EXECUTION_DISABLED` must not be `1`;
- the explicit `--confirm-paid-provider-call` command flag.

Missing or ambiguous configuration fails before client construction or network access. Normal
startup, tests, packet inspection, and `demo` never select OpenAI. For a future authorized first
live semantic pass over the demonstrated VAHomeMath evidence, run manually:

```bash
LLM_PROVIDER=openai \
LLM_MODEL=gpt-5.5 \
OPENAI_API_KEY="$OPENAI_API_KEY" \
GIS_PAID_EXECUTION_DISABLED=0 \
gis-intelligence live-opportunities \
  --tenant vahomemath \
  --site vahomemath \
  --entity-id 947737ce-fa06-49d5-8aef-b31fb914a828 \
  --confirm-paid-provider-call
```

That command performs one live structured generation and persists candidates only after the same
deterministic validation used by replay. Candidates remain human-review-required. The same
`OpenAILLMProvider` implements the recommendation and experiment proposal contracts after their
respective human gates; it does not create a parallel workflow.

The repository does not prescribe a model name because availability and authorization are
account-specific. Consult the official OpenAI model catalog and select a model supporting
Structured Outputs before an authorized live run.

## Database safety

Tests require explicit `TEST_DATABASE_URL` and never fall back to `DATABASE_URL`. Destructive
migration verification creates a unique `gis_migration_test_<run-id>` database, requires an
unforgeable run-matched internal authorization value, rejects persistent database names, rejects
the application database, and now rejects hosts outside the approved local/container test-host
allowlist. Uncertain identity fails closed before destructive SQL.

Epic 27 migration `20260907_0034` only creates tables and indexes on upgrade. It drops, renames,
type-changes, or backfills no pre-existing object and preserves all existing rows. Its downgrade
removes only the new Epic 27 objects and is exercised solely through the repository's positively
identified, run-owned disposable migration-test database.

Automated tests inject a mock Responses API client and the implementation demonstration uses
replay, so neither requires API credentials or network access. Paid provider calls for Epic 27
development and testing: **zero**.
