import {cleanup, render, screen, within} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import EvidencePage from "../app/evidence/page";
import {DomainEvidence} from "./domain-evidence";
import {SemanticDetail} from "./semantic-detail";

vi.mock("next/navigation", () => ({
  usePathname: () => "/evidence",
  useRouter: () => ({push: vi.fn()}),
  useSearchParams: () => new URLSearchParams(),
}));

const answer = (body: unknown) => Promise.resolve({
  ok: true,
  status: 200,
  text: () => Promise.resolve(JSON.stringify(body)),
} as Response);

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("entity-centered evidence", () => {
  it("loads generic source options and surfaces the canonical BuiltWith domain", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) =>
      String(input).includes("/evidence/options")
        ? answer({sources: [{value: "builtwith", label: "BuiltWith"}, {value: "ga4", label: "Google Analytics 4"}]})
        : answer({items: [{id: "domain-1", label: "vahomemath.com", entity_type: "DOMAIN", evidence_type: "TECHNOLOGY_PROFILE", classification: "PROVIDER_REPORTED_HISTORY", status: "OBSERVED", sources: ["builtwith"], fresh_through: "2026-09-04T20:38:09Z", gap_count: 0, href: "/evidence/domains/1"}], page: 1, limit: 25, total: 1}),
    ));
    render(<EvidencePage />);
    expect(await screen.findByRole("option", {name: "BuiltWith"})).toBeInTheDocument();
    expect(await screen.findByRole("link", {name: "vahomemath.com"})).toHaveAttribute("href", "/evidence/domains/1");
    expect(screen.getAllByText("Technology profile")).toHaveLength(2);
  });

  it("renders a grouped profile with honest dates, costs, credits, and provenance", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({
      label: "vahomemath.com",
      description: "Canonical domain intelligence.",
      summary: {entity_type: "DOMAIN", canonical_subject: "vahomemath.com", domain_type: "PRIMARY", primary_domain: true, sources: ["BuiltWith", "DataForSEO / external search"]},
      facets: {technology_profile: {source: "BuiltWith", observation_count: 1, technology_count: 1, collected_at: "2026-09-04T20:38:09Z", temporal_semantics: "Provider-reported detection history; current presence is unknown."}, search_domain_intelligence: {observation_count: 3, status: "AVAILABLE"}},
      technology_profile: {groups: [{category: "analytics", count: 1}], detections: [{id: "d1", technology_name: "Google Analytics", provider_technology_id: "1515850015", category: "analytics", first_seen: "2020-01-01T00:00:00Z", last_seen: "2026-08-01T00:00:00Z", status: "PROVIDER_REPORTED_HISTORY", current_presence: "UNKNOWN", source: "BuiltWith", collected_at: "2026-09-04T20:38:09Z", href: "/evidence/technology/d1"}]},
      collection_accounting: {records_received: 25, normalized_detections_inserted: 24, records_rejected: 0, explanation: "Two Google Analytics source signatures were preserved as one canonical detection."},
      cost_and_credits: {provider_requests: 1, provider_reported_credits_consumed: 1, provider_reported_credits_remaining: 1999, estimated_economic_cost: "0.04950000", actual_provider_usd_charge: null},
      provenance: {source: "/system/sources/builtwith", orchestration_run: "/system/runs/run-1", observation_id: "observation-1"},
      limitations: ["Provider history is not proof that a technology is currently installed."],
    })));
    render(<DomainEvidence id="domain-1" />);
    expect(await screen.findByRole("heading", {name: "vahomemath.com"})).toBeInTheDocument();
    const group = screen.getByRole("heading", {name: /analytics/i}).parentElement as HTMLElement;
    expect(within(group).getByRole("link", {name: "Google Analytics"})).toHaveAttribute("href", "/evidence/technology/d1");
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.getByText("$0.04950000 estimate")).toBeInTheDocument();
    expect(screen.getByText("Not reported")).toBeInTheDocument();
    expect(screen.getByText("1,999")).toBeInTheDocument();
    expect(screen.getByRole("link", {name: "Orchestration run"})).toHaveAttribute("href", "/system/runs/run-1");
  });

  it("renders technology provenance and a raw-evidence policy boundary", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({label: "Google Analytics", description: "Normalized detection", technology: {provider_category: "analytics", first_seen: "2020-01-01T00:00:00Z", last_seen: "2026-08-01T00:00:00Z", current_presence: "UNKNOWN"}, observation: {target_domain: "vahomemath.com", source: "BuiltWith"}, evidence: [{type: "PROVIDER_PAYLOAD", payload_hash: "hash"}], provenance: {orchestration_run: "/system/runs/run-1", source: "/system/sources/builtwith"}, raw_display: {status: "WITHHELD", reason: "Raw evidence is shown only when explicitly allowed."}})));
    render(<SemanticDetail endpoint="/api/v1/evidence/technology/d1" eyebrow="Technology evidence" fallback="Technology detection" />);
    expect(await screen.findByRole("heading", {name: "Google Analytics"})).toBeInTheDocument();
    expect(screen.getByText("WITHHELD")).toBeInTheDocument();
    expect(screen.getByRole("link", {name: "Orchestration run"})).toHaveAttribute("href", "/system/runs/run-1");
  });

  it("renders an empty technology-profile state without inventing detections", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({label: "empty.example", description: "Canonical domain intelligence.", summary: {entity_type: "DOMAIN", canonical_subject: "empty.example", domain_type: "OTHER", primary_domain: false, sources: []}, facets: {technology_profile: {source: "BuiltWith", observation_count: 0, technology_count: 0, collected_at: null, temporal_semantics: "No observations."}, search_domain_intelligence: {observation_count: 0, status: "NO_MATCHING_OBSERVATIONS"}}, technology_profile: {groups: [], detections: []}, collection_accounting: {}, cost_and_credits: {}, provenance: {}, limitations: []})));
    render(<DomainEvidence id="empty" />);
    expect(await screen.findByText("No BuiltWith technology observations are available for this domain.")).toBeInTheDocument();
  });
});
