import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import InvestigationsPage from "../app/seo-investigations/page";
import {SEOInvestigationDetail} from "./seo-investigation-detail";

vi.mock("next/navigation", () => ({
  usePathname: () => "/seo-investigations",
  useRouter: () => ({push: vi.fn()}),
  useSearchParams: () => new URLSearchParams(),
}));

const answer = (body: unknown, ok = true, status = 200) => Promise.resolve({
  ok, status, text: () => Promise.resolve(JSON.stringify(body)),
} as Response);

afterEach(() => {cleanup();vi.unstubAllGlobals()});

describe("guided SEO investigations", () => {
  it("renders deterministic conflict and closed stages with operator filters", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({items: [
      {id:"1",label:"VA calculator investigation",href:"/seo-investigations/1",query:"va down payment calculator",candidate_page:"https://vahomemath.com/va-entitlement-calculator",status:"CONFLICTING_EVIDENCE",priority:"HIGH",evidence_readiness:"CONFLICTING",human_review_required:true,recommendation_eligible:false},
      {id:"2",label:"Closed investigation",href:"/seo-investigations/2",query:"va loan",candidate_page:"https://vahomemath.com/",status:"CLOSED_NO_ACTION",priority:"LOW",evidence_readiness:"LIMITED",human_review_required:false,recommendation_eligible:false},
      {id:"3",label:"Blocked investigation",href:"/seo-investigations/3",query:"va refinance",candidate_page:"https://vahomemath.com/refinance",status:"BLOCKED",priority:"MEDIUM",evidence_readiness:"BLOCKED",human_review_required:true,recommendation_eligible:false},
    ],page:1,limit:25,total:3})));
    render(<InvestigationsPage/>);
    expect(screen.getByText("Loading current GIS state…")).toBeInTheDocument();
    expect(await screen.findByRole("link",{name:"VA calculator investigation"})).toHaveAttribute("href","/seo-investigations/1");
    expect(screen.getByText("Conflicting evidence")).toBeInTheDocument();
    expect(screen.getByText("Closed no action")).toBeInTheDocument();
    expect(screen.getByText("Blocked investigation")).toBeInTheDocument();
    expect(screen.getByLabelText("Stage")).toBeInTheDocument();
    expect(screen.getByLabelText("Evidence readiness")).toBeInTheDocument();
  });

  it("renders an honest empty state", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({items:[],page:1,limit:25,total:0})));
    render(<InvestigationsPage/>);
    expect(await screen.findByText("No SEO investigations match this scope")).toBeInTheDocument();
    expect(screen.getByText(/Missing does not mean zero/)).toBeInTheDocument();
  });

  it("renders guided detail in evidence order and collapses technical lineage", async () => {
    vi.stubGlobal("fetch", vi.fn(() => answer({
      label:"VA calculator investigation",description:"Does the candidate page satisfy the exact query?",
      stage:"AWAITING_HUMAN_REVIEW",stage_explanation:"A governed assessment awaits confirmation.",
      scope:{exact_query:"va down payment calculator",candidate_page:"https://vahomemath.com/va-entitlement-calculator",market_id:"market-1"},
      next_action:{action_type:"REVIEW_INTERPRETATION",label:"Complete required human review",explanation:"A governed interpretation awaits human confirmation.",requires_human_approval:true,may_incur_cost:false},
      evidence_readiness:{state:"SUPPORTED",owned_page_observations:1,exact_query_serp_observations:1},
      evidence_gaps:[{id:"gap-1",type:"QUERY_PAGE_INTENT",description:"Review intent.",resolved:true,adjudication:"SATISFIED"}],
      query_page_intent:{association:"SUPPORTED",targeting:"SUPPORTED",intent_satisfaction:"SUPPORTED"},
      human_review:{required:true,assessment_review:"UNREVIEWED"},recommendation_eligible:false,
      history:[{event_type:"CREATED",actor:"operator",previous_state:"DRAFT",new_state:"EVIDENCE_REQUIRED",reason:"Investigation scope was created.",occurred_at:"2026-09-12T12:00:00Z"}],
      technical:{investigation_id:"1",identity_hash:"secret-noise"},
    })));
    render(<SEOInvestigationDetail id="1"/>);
    expect(await screen.findByRole("heading",{name:"VA calculator investigation"})).toBeInTheDocument();
    expect(screen.getByRole("heading",{name:"What should I do next?"})).toBeInTheDocument();
    expect(screen.getByText(/Intent satisfaction:/)).toBeInTheDocument();
    expect(screen.getByText(/Recommendation generation: Not eligible/)).toBeInTheDocument();
    expect(screen.getByText("Technical lineage").closest("details")).not.toHaveAttribute("open");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("renders bounded API errors", async () => {
    vi.stubGlobal("fetch",vi.fn(()=>answer({error:{code:"SEO_INVESTIGATION_NOT_FOUND",message:"Investigation not found",request_id:"r",details:null,retryable:false}},false,404)));
    render(<SEOInvestigationDetail id="missing"/>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Investigation not found");
  });
});
