import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import {InterventionApproval, RecommendationReview} from "./decision-workflow";
import {OpportunityInbox} from "./opportunity-inbox";
import {OverviewPage} from "./overview";
import {SystemPage} from "./system";

function answer(body: unknown, ok = true, status = 200) {
  return Promise.resolve({ok, status, text: () => Promise.resolve(JSON.stringify(body))} as Response);
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("GIS Workbench", () => {
  it("renders the decision overview and preserves zero as a real count", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({opportunities_to_review: 0, recommendations_to_review: 2, interventions_to_approve: 1, active_interventions: 0, experiments_running: 0, recent_outcomes: 0, search: {stored_observations: 146, latest_observation: "2026-08-27", rights_state: "UNKNOWN", blocker: "rights review", clicks: null, impressions: null}, traffic: {stored_event_observations: 282, stored_landing_page_observations: 23, latest_observation: "2026-08-28", rights_state: "UNKNOWN", blocker: "rights review", sessions: null}, visibility: {stored_serp_observations: 1, stored_serp_results: 100}, market: {name: "VA Loan Calculator Search Market", version: 1, definition_member_count: 1, observation_count: 0}, demand: {stored_external_keywords: 10, demand_observations: 0, demand_signals: 0, rights_state: "UNKNOWN"}, evidence: {packages: 0, gaps: 0, status: "NOT_PRODUCED", explanation: "Rights review required."}, competitive: {content_observations: 2, technology_detections: 2, events: 4, latest_event: "2026-08-30"}, collection_health: {targets: 251, query_targets: 87, domain_targets: 75, url_targets: 89, latest_update: "2026-08-31"}, unknown_values_are_zero: false})));
    render(<OverviewPage/>);
    expect(screen.getByText("Loading current GIS state…")).toBeInTheDocument();
    expect(await screen.findByText("Intelligence overview")).toBeInTheDocument();
    expect(screen.getByText("Stored GSC observations").parentElement).toHaveTextContent("146");
    expect(screen.getByText("Recommendations to review").parentElement).toHaveTextContent("2");
    expect(screen.getByText(/acceptance creates a draft/i)).toBeInTheDocument();
  });

  it("renders the epistemically accurate opportunity empty state", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({items: [], page: 1, limit: 25, total: 0})));
    render(<OpportunityInbox/>);
    expect(await screen.findByText(/No evidence package currently satisfies/)).toBeInTheDocument();
    expect(screen.getByText(/exact conditions passed or failed/i)).toBeInTheDocument();
  });

  it("renders API failures instead of failing silently", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({error: {code: "CAPABILITY_UNAVAILABLE", message: "Capability unavailable", request_id: "r", details: null, retryable: true}}, false, 503)));
    render(<OpportunityInbox/>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Capability unavailable");
  });

  it("shows rights/provider status and unknown freshness without zero", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({items: [{schedule: "ai_recommendations", status: "DISABLED", latest_success: null, stale_since: null}], experience: {lab_observations: 8, field_observations: 0, crux_state: "NO_FIELD_DATA_AVAILABLE", semantics: "Lighthouse LAB observations are never represented as CrUX FIELD data."}, fixture_ai_provider: true, production_ai_operational: false})));
    render(<SystemPage/>);
    expect(await screen.findByText(/Fixture \/ development recommendation provider/)).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.getByText(/8 Lighthouse LAB observations/)).toBeInTheDocument();
  });

  it("accepts a recommendation only into a draft intervention workflow", async () => {
    const fetch = vi.fn()
      .mockImplementationOnce(() => answer({id: "r1", resource_type: "recommendation", data: {summary: "Consider a bounded change", candidates: [{id: "c1", rank: 1, validation_state: "VALID", rationale: "Contract fit", target_metric_key: "GSC_CLICKS", expected_direction: "INCREASE", feasibility: "UNKNOWN", measurement_readiness: "PARTIAL"}]}}))
      .mockImplementationOnce(() => answer({intervention_approved: false}))
      .mockImplementationOnce(() => answer({id: "r1", resource_type: "recommendation", data: {summary: "Consider a bounded change", candidates: []}}));
    vi.stubGlobal("fetch", fetch); render(<RecommendationReview id="r1"/>);
    fireEvent.click(await screen.findByRole("button", {name: /Accept candidate/}));
    expect(await screen.findByText(/DRAFT intervention was created; it is not approved/)).toBeInTheDocument();
  });

  it("keeps intervention approval on a separate screen and action", async () => {
    const fetch = vi.fn()
      .mockImplementationOnce(() => answer({id: "i1", resource_type: "intervention", data: {title: "Content intervention", status: "PROPOSED", feasibility: "UNKNOWN", measurement_readiness: "PARTIAL", constraints_json: [], risk_json: [], updated_at: "2026-08-31T12:00:00Z"}}))
      .mockImplementationOnce(() => answer({status: "APPROVED"}))
      .mockImplementationOnce(() => answer({id: "i1", resource_type: "intervention", data: {title: "Content intervention", status: "APPROVED"}}));
    vi.stubGlobal("fetch", fetch); render(<InterventionApproval id="i1"/>);
    fireEvent.click(await screen.findByRole("button", {name: "Approve intervention"}));
    await waitFor(() => expect(screen.getByText(/No execution was started/)).toBeInTheDocument());
  });
});
