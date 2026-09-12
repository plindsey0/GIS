import {cleanup,render,screen} from "@testing-library/react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {ContentBriefDetail} from "./content-brief-detail";
import {ContentBriefs} from "./content-briefs";

const answer=(body:unknown,ok=true,status=200)=>Promise.resolve({ok,status,text:()=>Promise.resolve(JSON.stringify(body))} as Response);
afterEach(()=>{cleanup();vi.unstubAllGlobals()});

describe("evidence-backed content briefs",()=>{
  it("shows every failed eligibility gate without generating",async()=>{
    const fetch=vi.fn((input:string)=>input.includes("brief-eligibility")?answer({eligible:false,failed_gates:[{gate:"ADJUDICATION",reason:"Required evidence gaps have no current adjudication."},{gate:"HUMAN_REVIEW",reason:"Human review remains incomplete."}]}):answer({items:[]}));vi.stubGlobal("fetch",fetch);
    render(<ContentBriefs investigationId="investigation-1"/>);
    expect(await screen.findByText(/Required evidence gaps/)).toBeInTheDocument();
    expect(screen.getByText(/Human review remains incomplete/)).toBeInTheDocument();
    expect(screen.queryByRole("button",{name:"Generate evidence-backed brief"})).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("labels eligible generation as explicit and non-publishing",async()=>{
    vi.stubGlobal("fetch",vi.fn((input:string)=>input.includes("brief-eligibility")?answer({eligible:true,failed_gates:[]}):answer({items:[]})));
    render(<ContentBriefs investigationId="investigation-1"/>);
    expect(await screen.findByRole("button",{name:"Generate evidence-backed brief"})).toBeInTheDocument();
    expect(screen.getByText(/explicit operator action/)).toBeInTheDocument();
    expect(screen.getByText(/No content change has been proposed or implemented/)).toBeInTheDocument();
  });

  it("renders draft proposals, non-claims, and collapsed lineage",async()=>{
    vi.stubGlobal("fetch",vi.fn(()=>answer({status:"READY_FOR_REVIEW",summary:"A governed draft; no page change is authorized.",exact_query:"va down payment calculator",candidate_url:"https://vahomemath.com/va-entitlement-calculator",market_id:"market-1",user_need:"Calculate a bounded VA down payment scenario.",recommended_page_role:"Editorial hypothesis only.",recommendations:{suggested_sections:[{text:"Draft task guidance.",nature:"EDITORIAL_HYPOTHESIS",supporting_reference_ids:["ref-1"]}],unchanged:[{text:"Preserve calculator logic.",nature:"EDITORIAL_HYPOTHESIS",supporting_reference_ids:["ref-1"]}],measurement:[{text:"Define baselines.",nature:"EDITORIAL_HYPOTHESIS",supporting_reference_ids:["ref-1"]}]},prohibited_claims:["will improve rankings"],assumptions:[],conflicts:[],limitations:["SERP depth is bounded."],remaining_gaps:[],next_action:"Review each bounded proposal.",review_dependencies:[{review:"EDITORIAL",required:true}],proposals:[{id:"proposal-1",status:"READY_FOR_REVIEW",category:"CONTENT_STRUCTURE",target_region:"page structure",current_observed_state:"No unrestricted claim.",proposed_instruction:"Draft structure.",expected_qualitative_effect:"Hypothesis requiring measurement.",risk:"Requires review.",supporting_reference_ids:["ref-1"]}],technical:{input_fingerprint:"hidden"}})));
    render(<ContentBriefDetail investigationId="investigation-1" briefId="brief-1"/>);
    expect((await screen.findAllByText("Draft editorial suggestion")).length).toBeGreaterThan(0);
    expect(screen.getByText(/Approval does not implement/)).toBeInTheDocument();
    expect(screen.getByText(/Must not claim: will improve rankings/)).toBeInTheDocument();
    expect(screen.getByText("Technical lineage").closest("details")).not.toHaveAttribute("open");
  });

  it("renders bounded errors",async()=>{
    vi.stubGlobal("fetch",vi.fn(()=>answer({error:{code:"CONTENT_BRIEF_NOT_FOUND",message:"Content brief not found",request_id:"r",details:null,retryable:false}},false,404)));
    render(<ContentBriefDetail investigationId="i" briefId="missing"/>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Content brief not found");
  });
});
