# BuiltWith technology profile intelligence

For operator inspection after collection, see the
[entity-centered Evidence Explorer](evidence-explorer.md). It documents canonical-domain
navigation, historical detection semantics, raw-display enforcement, provenance, credit
and cost labels, and the verified 25-source-entry to 24-canonical-detection accounting.

## Contract and conservative defaults

See [rights evidence and review](builtwith-rights-review.md) and
[WhoAmI account telemetry](builtwith-account-telemetry.md). The source page now supports
connection-scoped versioned human review and explicit, credit-free account refresh.
Neither operation queues a technology lookup. Rights recommendations are not approvals.

Dependency discovery follows both direct source links and site-scoped schedule connection
links. Provider-created pipelines previously omitted the direct source link, producing
a misleading unmapped boolean despite their connection binding. Missing registered asset
lineage is now explained separately; no historical schedule is rewritten to correct the display.

BuiltWith uses the normal provider → capability → authorized DOMAIN target → explicit
manual scope → confirmation → orchestration contract. `TECHNOLOGY_PROFILE` binds to
the `builtwith_technology` pipeline and `gis-builtwith sync` collector. The adapter
registration migration enables the implementation, not collection. No connection,
target authorization, schedule, rights grant, or live lookup is created by migration.
The configuration UI starts disabled/manual-only with editable request-limit
suggestions of 1 per execution, 1 per day, and 5 per month. Dollar ceilings and
pricing remain operator decisions. Limits are safety policy, not provider product caps.

Connection ≠ credential resolution ≠ authentication ≠ authorization ≠ execution readiness.
Authorized target ≠ selected target ≠ executed target. Both manual-only and scheduled
targets start unselected. A manual invocation never alters a recurring schedule.

## API and costs

The [Domain API](https://api.builtwith.com/domain-api) endpoint is
`https://api.builtwith.com/v23/api.json`. One root-domain request returns technology
names, IDs, categories, paths, and detection history without pagination. GIS requests
`NOMETA=yes`, `NOPII=yes`, and `NOATTR=yes` to avoid unnecessary contact/attribute data.
It does not request the extra-credit TRUST enrichment, live endpoint, bulk endpoint,
or any follow-up request. It retains historical technologies, so a returned detection
is provider-reported history, not proof of present deployment.

The [Free API](https://api.builtwith.com/free-api) supplies group/category counts and
dates, not named technology profiles. It is cheaper but cannot supply this capability's
named-technology requirement; GIS does not call it as a preliminary probe.

The [product catalog](https://builtwith.com/all-products) lists PAYG API credits
separately from web subscriptions: $99 for 2,000 credits, one credit per domain,
non-expiring credits, with volume pricing. That package implies $0.0495/credit only
for that purchase basis. It is not an account-verified actual charge and is not seeded
as pricing. The $295/$495/$995 web subscriptions are not inherently required for
Domain API access. Confirm current entitlement and pricing with BuiltWith before buying.

Provider documentation lists limits of 8 concurrent requests and 10 requests/second.
GIS uses one domain per execution, no automatic pagination or HTTP retries, and obeys
HTTP 429 via the existing bounded orchestration retry policy. Response credit and
rate-limit headers are retained as telemetry; cumulative credits-used is not a safe
per-request delta under concurrency. No additional balance request is made.

The Domain API does not document a per-response USD charge. Its `Spend` field estimates
the website's technology spend, not GIS API cost. Actual dollar cost therefore remains
UNKNOWN/unreconciled. Operator pricing can provide a Decimal estimate, not actual spend.
Request counts remain exact. Bounded unknown-cost permission is required without
pricing; hard dollar limits cannot guarantee unknown provider charges. A transport or
processing failure after dispatch also remains unreconciled rather than fabricating $0.

## Local connection and credentials

Install the repository editable package after pulling so `gis-builtwith` is available:

```sh
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/alembic upgrade head
.venv/bin/gis-builtwith configure --tenant vahomemath --site vahomemath \
  --credential-reference env:GIS_BUILTWITH_CREDENTIAL
```

Load the normal repository environment before database commands. The configure command
is explicit and idempotent; it creates an unreviewed tenant/site rights policy for a new
connection, records only a reference, and does not activate collection or call BuiltWith.

Supply a BuiltWith Domain API key with sufficient API-credit entitlement through the
`GIS_BUILTWITH_CREDENTIAL` environment variable. Supported values are a key string or
JSON `{"api_key":"YOUR_KEY"}`. Do not commit this value. Alternatively use the existing
local secret convention: `~/.config/gis/secrets/builtwith.env`, containing
`GIS_BUILTWITH_CREDENTIAL='YOUR_KEY'`. The file must be owned by the execution user,
not a symlink, and owner-only (0600); it is never sourced as shell code. Resolution
uses the shared credentials module and live worker attestation, without an auth probe.
Requests send the key in the documented Authorization header, not URLs; redirects
are disabled and provider error text is not persisted verbatim.

Open Data Providers → BuiltWith, choose the connection, explicitly authorize the
existing `vahomemath.com` DOMAIN, keep manual-only, and configure limits/pricing.
Rights require separate review before execution. Preview manual run opens an empty
selection; choose the domain, review 1 capability / 1 target / 1 request, then confirm
only when paid execution has been explicitly authorized. The validation hold must
remain on until that separately authorized live test.

## Evidence and governance

The adapter reuses TechnologyObservation, TechnologyDetection, TechnologyEvidence,
TechnologyAlias, IngestionRun, and ProviderUsageEvent. It records the complete returned
technology payload, category/path details, provider IDs/dates, hash, endpoint, collection
time, LICENSED_API acquisition, rights policy/version, and documented response telemetry.
Duplicate identical evidence is deduplicated, while the complete payload remains intact.
No historical observations are overwritten. Missing technologies are not asserted absent.

The existing worker links each scoped run and attempt to the collector's exact ingestion
ID, rather than guessing the latest connection ingestion. The usage ledger references
that ingestion, provider, and capability; the run stores target and actor/scope audit data.
Successful validated responses establish historical authentication without invented task IDs.

Raw and normalized retention must both be explicitly ALLOWED before dispatch because
this capability promises lossless source retention. Newly configured rights remain all
UNKNOWN, including AI training, redistribution, raw display, and cross-tenant learning.
Policy version/effective creation date and documentation basis are recorded; review date
and authority remain unset until an actual operator review. API entitlement grants no
inferred downstream uses. No live authentication was performed during implementation.

Rights review is an immutable two-step workflow. The operator edits explicit grants and
compatibility decisions, reviews proposed changes and collection impact, then confirms a
successor policy. The Workbench reloads authoritative policy, history, and source blockers
after commit. A stale policy ID, reused version label, invalid evidence field, or persistence
failure is explicit and preserves the draft. Close and reopen after a stale conflict to
compare the new effective version. Approval never triggers WhoAmI, domain collection,
scheduling, authorization, or credit spend.

## Failure semantics and tests

Missing/unsafe credentials → CONFIGURATION_ERROR / CredentialUnavailable.
HTTP 401 or BuiltWith -2 → AUTHENTICATION_FAILED; HTTP 403 → AUTHORIZATION_FAILED;
429 → PROVIDER_429; -3/-5 credits/plan exhaustion → BUDGET_BLOCKED; malformed payload →
UNKNOWN_TERMINAL; provider -99/5xx → PROVIDER_5XX. Internal processing errors remain
internal. See [provider error codes](https://api.builtwith.com/errorCodes).

`tests/test_builtwith.py` uses synthetic HTTP/profile fixtures only and covers parsing,
credential safety, failure classes, explicit scope, limits, and the complete worker →
attempt → ingestion → technology evidence → usage → activity chain. Live acceptance
requires an operator-provided key, entitlement, reviewed rights, and explicit approval.

The CLI returns the exact ingestion identifier even when ingestion fails, with a nonzero
exit status. The worker links that failed ingestion to the attempt and applies the shared
failure/retry policy. A successful process exit alone never establishes collection success.
The isolated `test_builtwith_acceptance.py` exercises this real CLI contract using mocked
HTTP responses; its records are not production authentication or acceptance evidence.

Documented offset-bearing ISO detection timestamps populate normalized first/last-seen
fields in UTC. Unrecognized, numeric, or timezone-less values remain in raw evidence,
with normalized dates unknown. Repeated technology paths use earliest first/latest last
dates. Provider history is not proof of current presence. Existing technology staging
models expose these observations and detections; opportunity qualification is unchanged.

## First live acceptance: operator checklist (not performed by this epic)

1. Review and merge the branch, install the editable package, and restart GIS.
2. Configure the secret reference above and verify worker credential resolvability.
   This does not validate the key with BuiltWith. Confirm Domain API entitlement separately.
3. Review rights with an identified authority. Explicitly permit raw and normalized
   retention only if licensed; leave other unreviewed uses UNKNOWN.
4. Configure BuiltWith → TECHNOLOGY_PROFILE → existing DOMAIN `vahomemath.com`.
   Keep **Manual only · Not scheduled**. No location/language parameters are required.
5. Set conservative hard budgets and explicit request limits (one per execution and
   one per day for this test). Enter pricing only on a documented basis. If actual/estimated
   price is unknown, explicitly review bounded unknown-cost permission; it is not free.
6. Activate BuiltWith collection. Check credential, authorization, rights, budgets and
   readiness separately. Do not alter DataForSEO settings or recurrence.
7. Release the process-level paid-execution hold only with explicit live-test approval.
   This is a global hold: inspect pending paid work first, since releasing it also permits
   already-authorized DataForSEO work. Restart with the approved runtime environment.
8. Preview manual run, select only `vahomemath.com`, review **1 capability / 1 target /
   1 provider request**, cost Known or Unknown, and no schedule impact. Preview spends nothing.
9. Explicitly confirm once. Follow activity → run → attempt → ingestion → technology
   evidence → usage. Verify endpoint v23, domain, timestamps, rights and source provenance.
10. Verify actual credit/cost telemetry if available. Cumulative credit headers and site
    `Spend` are not an exact request charge. Leave unresolved actual USD unknown; do not
    repeat a request merely to obtain billing evidence. Record acceptance separately.

If credentials, rights, budget or scope block preview, correct that specific control before
confirmation. For provider rejection inspect the classified cause and linked ingestion;
do not repeatedly click confirm. Rate-limit/transient failures may enter bounded retries:
inspect queued work and daily request controls before authorizing further attempts.
An empty technology profile can be a valid provider result; it does not justify synthetic
evidence or lowering detector thresholds.
