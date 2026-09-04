# BuiltWith account telemetry

Contract reviewed 2026-09-04 using BuiltWith's
[full API reference](https://api.builtwith.com/llms-full.txt) and
[compact reference](https://api.builtwith.com/llms.txt).

WhoAmI is `GET https://api.builtwith.com/whoamiv1/api.json`, using the same API key in
`Authorization: API …`. Official documentation explicitly states **no API credits used**.
The documented general limits are 10 requests/second and 8 concurrent requests.
Its response describes credits, rate limits, privacy flags and endpoint inventory;
account email/plan fields may also be present. Inventory is not proof of licensed entitlement.

GIS stores only normalized numeric balances/limits, recognized privacy flags and Domain
API inventory availability. It never stores the raw response, account email, key, or
provider URLs. Unknown values remain null. Errors use fixed classifications, never
provider response text. Redirects and HTTP retries are disabled. This is not a domain
target, ingestion run, evidence record or intelligence usage event.

Snapshots are append-only `gis_core.provider_account_telemetry` records, linked to a
tenant/connection, time and operator. No price assumption or dollar billing record is
created. Response balances do not override GIS request limits or budgets.

## Refresh and freshness

System → Sources → BuiltWith → Refresh account telemetry requires explicit confirmation
and administrator access. No page load, collector or scheduled task refreshes it.
There is a one-minute cooldown and a 24-hour display freshness threshold:

- UNKNOWN: never checked.
- CURRENT: latest successful check is within 24 hours.
- STALE: latest successful check is older; displayed values are historical.
- UNAVAILABLE: latest refresh failed; current balance is not inferred from old values.

The existing process paid-execution hold conservatively blocks this operation too,
despite its documented credit-free nature. Release it only through the normal operator
process after considering pending paid work. The technology collector does not depend
on fresh telemetry. No live refresh was made during implementation; mocks are not
authentication evidence. Live telemetry verification is a separate operator step.
