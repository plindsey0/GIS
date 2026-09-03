# Provider operations semantics

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
