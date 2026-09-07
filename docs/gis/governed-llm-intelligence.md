# Governed LLM intelligence v1

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
Evidence text is clearly labeled untrusted data in every prompt; instructions embedded in
collected content cannot change governance or lifecycle state. Confidence is model reasoning
metadata, not a calibrated probability.

## Architecture and lineage

`EvidencePacketService` selects at most 50 authoritative `evidence_package` records by explicit
tenant/site, IDs, condition, dates, and latest-N filters. It exposes stable IDs, entity context,
period, package items, source keys, rights state, quality-run provenance, and limitations. The
model never receives database access.

`LLMProvider.generate_structured` is the narrow provider boundary. `ReplayLLMProvider` returns
validated fixtures without network access or credentials. The three versioned prompts are
`opportunity_generation_v1`, `recommendation_generation_v1`, and `experiment_proposal_v1`.
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

## Provider-free operator workflow

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

The command prints the evidence packet, candidate opportunity, recorded human acceptance,
recommendation, recorded human selection, implementable experiment proposal, and complete
lineage. The provider fixture makes zero network and paid-provider calls. Invoking `demo` is the
operator's explicit request to record the two displayed human decisions; proposal approval remains
a separate future human decision.

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

Automated tests and the implementation demonstration require no API credentials. Paid provider
calls for Epic 27 development and testing: **zero**.
