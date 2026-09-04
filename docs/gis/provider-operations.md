# Provider operations semantics

See [Domain Search execution](domain-search-execution.md) for explicit location/language
configuration, ingestion-aware terminal outcomes, recorded versus effective failure,
and unknown-cost diagnosis. No historical records are rewritten by that interpretation.

## Explicit manual execution scope

Use **Preview manual run** to open a compact selector, grouped by capability.
Only enabled, authorized provider targets are offered. All targets start unselected,
including manual-only targets. Selecting a scheduled target explicitly
adds a manual execution without moving, replacing, or satisfying its scheduled work.
Review the capability, target and request totals, costs, and blockers, then confirm.
No target outside that reviewed scope is queued. An empty scope cannot execute.

A connection identifies access to a provider; a capability identifies a supported
collection type; an authorized target defines what that capability may observe.
A schedule governs recurring work. A manual scope is a one-time operator selection,
not a change to any of those authorizations or schedules. **Manual only / Not
scheduled** hides dormant clock values from the operational view.

Each selected target gets its own MANUAL run and existing attempt/ingestion/usage
links. Its configuration records the provider-target and capability-policy IDs,
one requested provider request, full reviewed scope, request ID, confirmation
fingerprint, and the current single-admin actor (`workbench-admin`). Queueing is
not provider usage: the existing collector reserves and reconciles actual usage
when execution occurs. Unknown estimated cost is not a recorded zero actual cost.
Current rights, target validity, credential/readiness, pause, and budget controls
are checked again before execution. Preview does not reserve credits.

## API contract and future jobs

`POST /api/v1/providers/{key}/run` accepts `request_id`, `target_ids` (authorized
ProviderCollectionTarget UUIDs), `confirmed`, and `fingerprint`. Omitted/empty
target IDs are rejected by the execution endpoint; use GET manual-scope for discovery.
The server never silently selects targets. Confirmation binds the
scope to the current configuration; changed scope requires another preview, and
a queued request ID cannot be reused for a different scope. Repeated confirmation
is idempotent. Targets are resolved within the requesting tenant/site/provider.

The per-run ceiling applies to each one-target execution; daily/monthly limits
also cover the whole selected batch. Execution-time reservations remain authoritative
under concurrency. This is not a new collection-job framework. Future independently
configured jobs can reuse explicit scope and attribution without reintroducing
provider-wide implicit execution.

## Discovery versus preview (16B.3.1)

`GET /api/v1/providers/{key}/manual-scope` is the dedicated choice-discovery contract.
It returns `scope_contract_version` and authorized choices, not an empty execution
summary. The UI renders capability-grouped checkboxes from that response, then calls
the POST preview only after explicit selection. Scope changes clear the prior preview.
An incompatible discovery response displays an actionable API/UI restart error.
Legacy POST-without-scope clients receive a clear reload/selector error instead of
an apparently valid zero-request/$0 confirmation screen.

The reported zero-request/$0 screen is consistent with a legacy summary-only UI consuming
the empty-scope response introduced in 16B.3. Current main's source and both generated
local bundles contained the selector; no DOMAIN/cadence exclusion was found. The earlier
browser's exact loaded bundle was not available to establish a cache/process root cause.
This is a verified contract ambiguity, not evidence that an authorized target disappeared.
Discovery and executable preview are now separate contracts and are tested separately.

See [BuiltWith](builtwith.md) for the shared technology-profile integration and its
credential, rights, billing, and live-acceptance boundaries.

## Pre-change audit (Epic 16B.2)

Base: `8d3782ab0f61430fef53508feb084028ff9b4940`; database head: `20260903_0030`.
The run retained its first start across retries, while its completion advanced to
the final attempt. Subtracting those values measured wall-clock resolution, not
execution. Attempt timestamps already preserve each active interval. Provider
usage stores Numeric(20,8) Decimal costs; display rounding does not change accounting.
The existing recovery has two attempts and an ingestion with provider task/cost
evidence. It must not be recreated, retimed, or recategorized in storage.

Collection schedules expand into one durable obligation/execution per authorized
target. DataForSEO SERP uses one target request per execution; retries are attempts
under that obligation, not new activity rows. Planning recommendations and provider
authorization remain separate. The default run page previously rendered raw fields
and policy objects without distinguishing operational information from audit data.

## Timing contract

- Attempt duration: completed minus started for that attempt; missing or invalid
  intervals remain unknown.
- Active execution / run duration: sum of attempt intervals only when all attempts
  have known durations. Successful attempt duration is shown separately.
- Wall-clock resolution: first attempt start to final terminal completion, including
  idle waiting; never labelled runtime.
- Lateness: positive satisfied-at minus obligation due-at.
- Recovery latency: lateness only where a failed attempt preceded success.

## Trust and disclosure

Connection configuration, worker resolution, historical authentication evidence,
collection authorization and execution readiness are independent. A successful
ingestion with real provider task evidence establishes endpoint authentication at
that time, not permanent credential validity or rights. Later authentication failure
supersedes that state. Merely resolving a secret never validates authentication.

Activity is a read-only view of runs, attempts, obligations, ingestion and usage.
Exact actual costs remain Decimal strings. Display rounding is explicitly separate;
unknown, estimated and reserved costs are not actual spend. No new historical
events or redundant persisted timing values are created.

Decision information stays visible; execution/data explanations are one disclosure
away; technical IDs, full rights, raw metadata and audit history are deliberate
advanced disclosures. Current incidents exclude satisfied obligations. Historical
recovered-late counts remain visible without misleading tiny-sample percentages.
