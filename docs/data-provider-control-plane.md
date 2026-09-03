# Data provider control plane

See [Provider configuration and execution binding](gis/provider-configuration.md)
for the guided workflow, derived schedules, manual confirmation and scoped pricing.

The provider control plane separates technical access from authorization. A connection says GIS can authenticate; a collection policy says whether GIS may call that provider, for which capability and targets, at what cadence, and within which limits. Credentials remain in the existing secret-reference mechanism.

## Safety model

- Commercial providers default to disabled. Adding credentials never activates spend.
- Provider, connection, policy, capability, target, pricing, and usage are separate records.
- Enablement requires an implemented adapter, an active connection, at least one explicitly configured policy, and a monthly hard budget for commercial providers.
- Every paid operation must call the centralized preflight before the external request. Preflight checks provider state, capability authorization, exact target scope, request limits, and daily/monthly/per-run budgets.
- Unknown prices fail closed. An operator can permit unknown cost only together with an explicit per-run request ceiling.
- Successful preflight can reserve projected cost transactionally. Reservations count against limits, preventing concurrent runs from independently consuming the same remaining budget.
- Completion reconciles a reservation to provider-reported or estimated actual cost. Usage rows and policy audit events are append-oriented.
- Disabling or pausing collection preserves the connection, historical data, usage ledger, and audit trail.

Soft limits produce warnings; hard limits block before a provider call. Budget periods use the policy timezone and persisted event timestamps remain timezone-aware UTC. Money uses PostgreSQL `numeric(20,8)` and Python `Decimal`; no floating-point arithmetic is used.

## Provider inventory

The registry includes Google Search Console, GA4, Google PageSpeed/CrUX, DataForSEO, Semrush, BuiltWith, and WhoisXMLAPI. Capabilities identify whether manual, scheduled, and targeted collection are supported. `IMPLEMENTED`, `PARTIAL`, and `PLANNED` describe adapter availability without pretending planned integrations are callable.

The Workbench **Data Providers** page shows connection and collection state independently, capability and target scope, last/next collection, recent usage, pricing semantics, spend, and blockers. Enabling is an explicit confirmed action. Admin API mutations write actor-attributed audit events; read-only roles can inspect inventory and detail but cannot change authorization.

## API and collector contract

The `/api/v1/providers` endpoints provide inventory, detail, policy, capability, target, action, and preflight operations. Callers scope every operation by tenant and site. Provider adapters should follow this sequence:

1. Calculate bounded request/unit estimates without making the external call.
2. Request preflight with the provider key, capability key, and exact target values.
3. Create a reservation in the same transaction used to authorize the run.
4. Call the provider only when `can_execute` is true.
5. Reconcile the reservation with actual provider cost and ingestion-run provenance, or mark it failed.

Provider-specific request construction belongs in adapters, not the generic policy service. A future adapter must register its provider and capabilities, use existing credential connections, expose explicit pricing provenance when known, and add preflight/reconciliation tests before marking a capability implemented.

## Analytics and operations

`mart_provider_usage_daily` reports governed requests, units, cost semantics, and active reservations. `mart_provider_budget_status` compares current-month consumption to configured policy limits. Provider-reported cost remains distinguishable from GIS estimates; unknown cost is never represented as zero.

Operational troubleshooting begins with the detail page blocker code: connection missing/invalid, policy disabled/paused, adapter unavailable, pricing unknown, capability disabled, target unauthorized, or a request/cost limit exceeded. Emergency pause stops authorization without deleting configuration.

## Migration and rollback

Migration `20260902_0029` creates and seeds registry metadata. It carries forward active free/customer-connected sources into enabled policies so existing collection behavior is preserved. It deliberately creates no commercial policy. Downgrade removes only control-plane tables and does not remove existing source connections or observations.
