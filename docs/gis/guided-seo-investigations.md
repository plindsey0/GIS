# Guided SEO investigations

Epic 29A provides a durable operator workspace for one bounded SEO question. It assembles existing governed facts without collecting data or generating recommendations from a read:

```text
Observe → Adjudicate → Interpret → Recommend → Approve → Implement → Measure
```

An investigation fixes one tenant, site, exact-query entity, candidate-page entity, and market definition. Active identity is exact and deterministic; lexical similarity never merges investigations. Closing an investigation permits a later explicit investigation of the same scope while preserving the earlier audit history.

## Lifecycle and readiness

The service derives the visible stage from current governed evidence gaps, collection requirements, Epic 28E adjudications, query/page/intent assessments, and append-only reviews. Missing, limited, conflicting, and blocked evidence remain distinct. Collection completion never implies satisfaction, query/page association never implies targeting or intent satisfaction, and a recommendation is never generated automatically.

Only complete gates can expose the explicit **Mark ready for recommendation** action. That action records an event and permits a later human-initiated recommendation workflow; it does not call a model or create a recommendation. Closing and reopening also require explicit, reasoned actions and preserve append-only events.

## Workbench

- `/seo-investigations` lists and filters investigations by search, stage, priority, evidence readiness, human-review requirement, and recommendation eligibility.
- `/seo-investigations/{id}` shows exact scope, stage explanation, one safe next action, evidence readiness, gaps and adjudications, owned-page and SERP coverage, query/page/intent states, reviews, history, and collapsed technical lineage.

Navigation and review actions are separate from execution. Collection-related queue items point operators to governed predecessor workflows and do not collect. Paid implications remain visible through collection-requirement cost class and existing provider controls.

## API

- `POST /api/v1/seo-investigations` creates or exactly replays a bounded active investigation.
- `GET /api/v1/seo-investigations` lists filtered investigations.
- `GET /api/v1/seo-investigations/action-queue` returns one current safe action per investigation in stable priority/severity/time/identity order.
- `GET /api/v1/seo-investigations/{id}` reads guided detail.
- `GET /api/v1/seo-investigations/{id}/actions` reads that investigation's action queue.
- `GET /api/v1/seo-investigations/{id}/history` reads immutable event history.
- `POST /api/v1/seo-investigations/{id}/actions` applies an allowed explicit lifecycle action.

Every endpoint is tenant/site scoped. GET requests are side-effect free and never invoke collection, a provider, an LLM, a recommendation, an experiment, or an intervention.
