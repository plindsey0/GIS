# Domain Search execution and failure diagnosis

## Explicit search market

GIS uses DataForSEO Labs Google Ranked Keywords:
`POST https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live`.
It returns keywords a domain ranks for, not a live query SERP collection.

The [official contract](https://docs.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live/)
requires `target`; location and language are optional at the provider level. Omitting
them can request all-location/all-language results. GIS deliberately requires an
explicit search market rather than silently broadening collection. The historical
"DataForSEO Labs requires a location target" message was a GIS validation exception,
not a provider response.

In Data Providers → DataForSEO → Configure collection → Schedule, the Domain Search
capability exposes **Search location code** and **Search language code**. For an
operator-approved United States / English market, enter `2840` and `en`. Neither is
automatically chosen. Values are scoped to the tenant/site capability policy, included
in configuration audit/fingerprints, shown in manual preview, and stored in new
ingestion metadata. Existing configurations without a market are blocked before dispatch.

The binding supplies `--location-code` and `--language`. The request body is a one-task
array with target, location_code, language_code, limit (currently 100), and the existing
organic/featured-snippet/local-pack item types. No alternative endpoint, pagination,
clickstream enrichment, or additional request is introduced. Direct CLI use also supports
`--location-name` instead of `--location-code`; these are mutually exclusive.

**Scheduling caution:** saving provider configuration reconciles its schedules. During
Epic 16B.32 no live configuration is saved, so the September 4, 7 AM America/New_York
SERP recurrence is preserved exactly. Configure the Domain Search market in a separately
reviewed operator step; do not alter the scheduled SERP acceptance test.

## Terminal-state contract

A zero-exit collector process alone is not evidence of successful collection. A linked
required ingestion must be SUCCEEDED with zero errors before the worker marks its
attempt/run successful. A failed, incomplete, or error-bearing required ingestion fails
the attempt and propagates a classified terminal failure or bounded retry according to
the existing policy. Zero received records plus an exception is never success; a valid
zero-record response without errors can still succeed.

External Search CLI returns nonzero for failed ingestion and returns its exact ingestion
identifier. The worker uses that identifier, validates tenant/site/connection scope, and
retains linkage and known cost on failure. It does not guess the latest connection ingestion.
Missing market/credentials are configuration errors; provider auth, quota, network and
HTTP failures retain their categories; malformed data and processing failures are not
silently counted as successful collection.

## Recorded versus effective history

Historical records are not rewritten. If a recorded SUCCEEDED run points to failed or
error-bearing ingestion, Workbench derives **Failed**, displays the classification/cause,
and explicitly explains that the original recorded state was SUCCEEDED. Attempt timelines
similarly distinguish effective and recorded status. Failure/success filters use the same
interpretation. Raw recorded evidence remains expandable.

Open a run from provider activity. Check Result, Classification, Errors, Records,
Provider requests, and Provider cost first, then inspect ingestion and recorded attempt
evidence if needed. This interpretation is evidence-based, not fabricated history.

## Cost and the September 3 failure

Run `5f0010bc-c85d-528a-ab50-a6755ee30758` links ingestion
`68dac7a5-00b7-46b1-85ab-7a8e30da67cb`. Its recorded usage is FAILED, request_count=1,
actual_cost=NULL, estimated_cost=NULL, semantics=UNKNOWN. The location validation occurs
before HTTP dispatch in that adapter path; no provider task/cost response is present.
The historical request count is a recorded execution/ledger count, not proof of a billable
HTTP request. None of these historical values are changed to zero or success.

For future failures, documented returned task costs (or a collected response cost before
local processing fails) retain Decimal precision. Without such evidence actual cost stays
UNKNOWN. Terminal reconciliation releases the active reservation according to the existing
ledger contract while preserving estimated cost separately; unknown charges are not zero.
Each attempted dispatch has its own ledger row; retries do not reuse or duplicate the
original reconciliation. This repair makes no calls to determine historical cost.

## Regression checks

`tests/test_domain_execution.py` covers binding, missing market, successful/failed ingestion,
exact CLI linkage, classifications, ledger costs/counts, schedule isolation, and read-only
historical interpretation. Existing manual-scope tests retain domain-only/query-only/mixed
scope and unselected scheduled targets. All provider executions in tests are fixtures.
