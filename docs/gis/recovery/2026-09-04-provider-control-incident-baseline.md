# Provider-control incident forensic baseline

Captured at 2026-09-05 00:20 UTC before recovery writes on
`codex/epic-26a-opportunity-collection-sufficiency`, Git
`0c5b314e48328d35a384980b7bb439473f034903`. The working tree contained the preserved,
uncommitted Epic 26A implementation. PostgreSQL was `localhost:5433/gis`; Alembic current
and head were `20260904_0032`. Schemas were `gis_core`, `gis_raw`, `gis_staging`,
`gis_intermediate`, and `gis_analytics`. No credential value is included here.

The damaged state was archived before any recovery write at
`~/.local/share/gis/backups/gis-pre-recovery-20260904-20260905T002054Z.dump`.
The PostgreSQL 16 custom archive is 1,809,365 bytes and passed `pg_restore --list`.

## Confirmed affected state

| Table | Pre-incident rows | Baseline rows | Baseline SHA-256 |
| --- | ---: | ---: | --- |
| `provider_account_telemetry` | 2 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `provider_capability` | 9 | 9 | `847e2e639cf1d7caf4eacd5ced5051570321c4a26ab33b8ace8632d6a733d5ee` |
| `provider_capability_policy` | 7 | 4 | `67797ed1cac87bfef36003376eb137c343afa866b2bd7c460958769df3a4f26b` |
| `provider_collection_policy` | 5 | 3 | `78da7eec99262b54fd4138d198496f7cd02700443c4ca875dd20d0ec8267b459` |
| `provider_collection_target` | 3 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `provider_definition` | 7 | 7 | `b6bdce597f5750e8ec07b9ce2e531f7d475f055143959bdde7dc102a38a76b26` |
| `provider_policy_audit_event` | 51 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `provider_pricing_configuration` | 13 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `provider_usage_event` | 6 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

## Protected surviving state

| Table | Rows | SHA-256 |
| --- | ---: | --- |
| `data_rights_policy` | 12 | `067ed0dd1a1b1ffd80f863f575001b31143ce5c90c1c117b1e43ff51791cb895` |
| `data_rights_grant` | 138 | `fedb5ecec5a79a80be82b3922092dd9ac1da7e93668546d4d891c3afb3eeecb8` |
| `data_source_connection` | 8 | `79ec8aaff91ba27977715a17753bbf6505185e38ab0ef759e21d28941823b73d` |
| `schedule_definition` | 20 | `5f0954d7cb1e62e2d2d311df5c610d7894bd91e2d59ab5da8e53a2d847f293ec` |
| `orchestration_obligation` | 25 | `896cf810a902cfccb20c614327b2ebdffc0fe94c243a802e1b01c0024baa55af` |
| `orchestration_run` | 36 | `e5c3605d13ee2d064d8910118ae62e4d564dd0003d80364bac190007f68617b5` |
| `execution_attempt` | 40 | `7949f53a9baade64bc6b2029309ca73f4db8d73fc1075906bc3f64180a1fde8e` |
| `ingestion_run` | 101 | `dbf7733eae6363bbd68af754c42122d7cdbdb24da30871d4002094faeba2de43` |
| `evidence_package` | 20 | `73317f18ec0a13a26c7852abe216c9caabcc7acea932eee790a67d33b66c6915` |
| `evidence_package_item` | 130 | `e7f6f3239253135d2811d01c322b11645a08afe7286b0fe934817625036b16e0` |
| `evidence_gap` | 10 | `77a69fc4014c458a25173bf1b77a5321f36b4d88d9629578b5f0fc93f121c54b` |
| `opportunity` | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `intervention` | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| `experiment` | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

Surviving operational evidence includes 20 schedules, 25 obligations, 36 runs, 40
attempts, 101 ingestion runs, 20 evidence packages, 130 package items, and 10 gaps.
Both DataForSEO and BuiltWith connections remain active with credential references present;
no credential was resolved or displayed. The DataForSEO weekly SERP schedule remains enabled
for Friday 07:00 America/New_York with next recurrence 2026-09-11 11:00 UTC. Its two prior
obligations remain satisfied. DataForSEO Domain Search and BuiltWith schedules remain disabled.

The BuiltWith reviewed rights policy survives and permits raw retention, normalized
retention, internal deterministic analysis, derivative creation, and aggregate statistics.
Other unreviewed uses remain UNKNOWN. DataForSEO's reviewed policy also survives.

## Root cause

`tests/conftest.py` configured Alembic with `TEST_DATABASE_URL`, but `migrations/env.py`
unconditionally replaced that setting with inherited `DATABASE_URL`. The test session fixture
then called `command.downgrade(config, "base")` during teardown. With development
`DATABASE_URL` present, Alembic operated on `gis`, not `gis_test`. There was no positive
disposable-database assertion, no destructive-test authorization token, and no denylist.
Subsequent upgrades recreated migrations 0029–0032 and their seed rows at 2026-09-04
22:39:32 UTC, but could not recover operational rows.

The lost 51 audit events, 6 usage events, 2 account telemetry snapshots, original UUIDs,
timestamps, and policy/pricing/target transition history are permanently incomplete and
must not be recreated. Forty-eight analytics relations had also been rebuilt against the
damaged state; they are derived and will be regenerated after current-state reconstruction.
