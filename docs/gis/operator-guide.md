# GIS operator guide

> Local-development recovery notice: provider-control history before September 4, 2026 is
> incomplete. Current DataForSEO and BuiltWith configuration is valid from the recovery
> boundary forward. Use surviving run and ingestion evidence for earlier activity; do not
> interpret the reset usage ledger as lifetime zero. See the
> [recovery report](recovery/2026-09-04-provider-control-recovery.md).

Start with Overview and System health, then inspect Market, Evidence, Collection, and Opportunities. Empty opportunities can be correct: a real evidence package must pass every published detector hard gate.

## Producing the first legitimate opportunity

1. Open **Opportunities → Detector sufficiency**.
2. Select a closest candidate and inspect required versus observed values.
3. Treat `FIRST_OBSERVED` as a request for real longitudinal history, never permission to duplicate data.
4. Review evidence gaps and the bounded collection plan.
5. Confirm rights, provider configuration, authorization, budget, and cadence in existing control-plane views.
6. Explicitly approve any operational change in its authoritative workflow.
7. After real observations arrive, run existing deterministic processing and re-evaluate without another provider call.
8. Run production opportunity detection only when every gate genuinely qualifies.

Never synthesize evidence, weaken thresholds, fabricate provider history, treat `UNKNOWN` rights as permission, or retry a paid source merely to make an opportunity appear. Recommendation review and intervention approval remain separate human decisions.

See [opportunity sufficiency](opportunity-sufficiency.md), [collection sufficiency](collection-sufficiency.md), and [target portfolio](target-portfolio.md).
