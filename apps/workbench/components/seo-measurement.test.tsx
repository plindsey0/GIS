import {cleanup,render,screen} from "@testing-library/react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {SEOMeasurementDetail} from "./seo-measurement-detail";
import {SEOMeasurementPlans} from "./seo-measurement";

const answer=(body:unknown)=>Promise.resolve({ok:true,status:200,text:()=>Promise.resolve(JSON.stringify(body))} as Response);
afterEach(()=>{cleanup();vi.unstubAllGlobals()});

describe("governed SEO measurement",()=>{
  it("renders a provider-free empty workflow",async()=>{
    const fetch=vi.fn(()=>answer({items:[]}));vi.stubGlobal("fetch",fetch);
    render(<SEOMeasurementPlans investigationId="i"/>);
    expect(await screen.findByText("No measurement plan yet")).toBeInTheDocument();
    expect(screen.getByText(/does not collect data/)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("renders bounded outcomes without causal language",async()=>{
    vi.stubGlobal("fetch",vi.fn(()=>answer({status:"MIXED_OR_CONFLICTING",exact_query:"va down payment calculator",candidate_url:"https://vahomemath.com/va-entitlement-calculator",market_id:"US",implementation:{state:"IMPLEMENTED",claimed_at:"2026-08-01",concurrent_changes:["Navigation update"],verification:"VERIFICATION_REQUIRED"},baseline:{state:"BASELINE_READY",observation_count:2,impressions:"100"},observation_window:{start:"2026-08-02",end:"2026-08-31"},primary_signals:["GSC_CLICKS"],secondary_signals:["GSC_CTR"],guardrails:["QUERY_PAGE_SCOPE"],current_outcome:{id:"outcome-1",outcome:"MIXED_OR_CONFLICTING",interpretation:"Observed after the change; causality is not established.",causal_classification:"CAUSALITY_NOT_ESTABLISHED",comparisons:[{signal:"GSC_CLICKS",baseline:"10",post:"20",direction:"INCREASE"}],limitations:["Low volume"],next_action:"Human review required."},limitations:["Observational only"],confounders:["Seasonality"],next_action:{label:"Review bounded outcome"},human_reviews:[],technical:{identity_hash:"hidden"}})));
    render(<SEOMeasurementDetail investigationId="i" planId="p"/>);
    expect((await screen.findAllByText("va down payment calculator")).length).toBe(2);
    expect(screen.getByText(/causality is not established/i)).toBeInTheDocument();
    expect(screen.getByText("Technical lineage").closest("details")).not.toHaveAttribute("open");
  });
});
