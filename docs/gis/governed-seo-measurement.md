# Governed SEO measurement

Epic 29C turns an approved Epic 29B page-change proposal into an explicit, versioned observational measurement workflow. It does not publish content, deploy code, collect provider data, create interventions, or make LLM calls.

The operator flow is: check proposal eligibility, explicitly create a plan, validate a compatible pre-change baseline, explicitly record implementation, wait for the defined observation window, select already-ingested governed evidence, run the deterministic assessment, and add an append-only human review. Closing and reopening are also explicit reviewed actions.

Plans retain tenant, site, exact query, normalized owned URL, market, country, language, device, search engine, dates, signal definitions, evidence requirements, risks, confounders, assumptions, limitations, and stable lineage. Exact replay is idempotent; a material timing or signal change creates a linked version.

The first supported comparison method is `GSC_QUERY_PAGE_PRE_POST` at `seo_measurement_v1`. A Search Console observation is usable only when its tenant/site, exact query, page, date, country/device/search type, rights policy, and quality are compatible. Unknown, blocked, or out-of-scope IDs fail closed. The implementation window cannot be used as baseline evidence.

Outcomes deliberately distinguish awaiting data, insufficient data, observed increase/decrease/stability, mixed evidence, inconclusive, and closed states. They preserve absolute and relative comparisons where valid, counts, quality, conflicts, limitations, and concurrent changes. The default causal classification is `CAUSALITY_NOT_ESTABLISHED`; an after-change association is never represented as proof that the change caused the result.

The Workbench routes are `/seo-investigations/[id]/measurement` and `/seo-investigations/[id]/measurement/[plan_id]`. Read routes are side-effect free. Mutation APIs require the existing review role and an explicit POST.

For the provider-free VAHomeMath scenario, use the exact query `va down payment calculator`, candidate page `https://www.vahomemath.com/va-entitlement-calculator/`, and the governed US/en/desktop market. Use only previously ingested, rights-approved evidence; do not fetch the live site or invoke a paid provider.

Verification remains provider-free:

```bash
export GIS_PAID_EXECUTION_DISABLED=1
export TEST_DATABASE_URL=postgresql+psycopg://gis:gis@localhost:5433/gis_test
.venv/bin/pytest -q tests/test_seo_measurement.py tests/test_content_briefs.py tests/test_seo_investigations.py
.venv/bin/ruff check .
.venv/bin/mypy src
cd apps/workbench && npm test && npm run lint && npm run typecheck && npm run build
```
