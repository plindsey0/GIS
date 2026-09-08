import {render, screen} from "@testing-library/react";
import {beforeEach, describe, expect, it, vi} from "vitest";
import {SemanticDetail} from "./semantic-detail";

describe("query-page-intent detail", () => {
  beforeEach(() => {
    localStorage.setItem("gis-context", JSON.stringify({tenant_id: "tenant", site_id: "site"}));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({
        label: "va down payment calculator ↔ candidate page",
        exact_query: {query: "va down payment calculator", market: "US / en / desktop"},
        candidate_page: {url: "https://vahomemath.test/va-entitlement-calculator/", content_freshness: "Current"},
        relationship: {association: "SUPPORTED", targeting: "PARTIAL", intent_satisfaction: "UNRESOLVED"},
        supporting_evidence: [{source: "exact-query GSC association"}, {source: "owned-page title and headings"}],
        conflicts: [{summary: "SERP is more calculator-oriented than the observed page"}],
        evidence_gaps: [{gap_type: "PAGE_FUNCTIONALITY_NOT_OBSERVABLE", status: "UNRESOLVED"}],
        audit: {provider: "replay", prompt_version: "query_page_intent_resolution_v1", llm_run_id: "run-id"},
      }),
    } as Response));
  });

  it("keeps association, targeting, satisfaction, evidence, conflicts and audit readable", async () => {
    render(<SemanticDetail endpoint="/query-page-intent/id" eyebrow="Query ↔ Page ↔ Intent" fallback="Relationship"/>);
    expect((await screen.findAllByText("va down payment calculator ↔ candidate page")).length).toBeGreaterThan(0);
    expect(screen.getByText("SUPPORTED")).toBeInTheDocument();
    expect(screen.getByText("PARTIAL")).toBeInTheDocument();
    expect(screen.getAllByText("UNRESOLVED").length).toBeGreaterThan(0);
    expect(screen.getByText("exact-query GSC association")).toBeInTheDocument();
    expect(screen.getByText("SERP is more calculator-oriented than the observed page")).toBeInTheDocument();
    expect(screen.getByText("query_page_intent_resolution_v1")).toBeInTheDocument();
  });
});
