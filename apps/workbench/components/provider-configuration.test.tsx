import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import {ProviderConfigurationPage} from "./provider-configuration";

const configuration={detail:{name:"DataForSEO",description:"Commercial search intelligence",implementation_status:"IMPLEMENTED",is_commercial:true,connection_state:"CONNECTED",collection_state:"CONNECTED_DISABLED",blocking_reason:"POLICY_DISABLED",budget:{spent_day:"0",spent_month:"0"},usage:[],last_collection:null,next_collection:null},policy:{timezone:"America/New_York",data_source_connection_id:"connection-1",monthly_hard_budget:"30",per_run_hard_budget:"5"},capabilities:[{key:"SERP_COLLECTION",name:"SERP collection",description:"Search results",enabled:true,target_ids:[],choices:[{id:"query-1",label:"va loan calculator",type:"QUERY"}],cadence:"WEEKLY",hour:8,minute:0,weekday:1,month_day:1,freshness_hours:168,per_run_limit:100,unit_price:null,pricing_notes:"",pricing_provenance:"UNKNOWN",last_verified:null}],connections:[{id:"connection-1",label:"Existing DataForSEO connection",status:"ACTIVE"}],history:[],schedules:[]};
function response(body:unknown){return Promise.resolve({ok:true,status:200,text:()=>Promise.resolve(JSON.stringify(body))} as Response)}
afterEach(()=>{cleanup();vi.unstubAllGlobals()});

it("puts decision information first and keeps the audit history collapsed",async()=>{
  vi.stubGlobal("fetch",vi.fn(()=>response({...configuration,detail:{...configuration.detail,operational_health:"HEALTHY",credential_readiness:{state:"CONNECTED_AND_RESOLVABLE",authentication_state:"VALIDATED",reason:"Historical provider acceptance"},operations:{activity:[],current_incidents:0,reliability:{expected:1,on_time:0,recovered_late:1,missed:0}}}})));
  render(<ProviderConfigurationPage providerKey="dataforseo"/>);
  expect(await screen.findByText("No current collection incidents.")).toBeInTheDocument();
  expect(screen.getByText("Validated by provider interaction")).toBeVisible();
  expect(screen.getByText("Configuration, governance and audit history").closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText("Targets and purpose: SERP collection").closest("details")).not.toHaveAttribute("open");
});

it("selects canonical targets, previews, and saves disabled without queuing collection",async()=>{
  const fetcher=vi.fn((url:string,options?:RequestInit)=>response(url.includes("/preview")?{can_activate:false,blockers:["Configure pricing"],plans:[],estimated_requests_month:"4.345",estimated_cost_month:null,timezone:"America/New_York",semantics:"Estimated"}:options?.method==="PUT"?{}:configuration));
  vi.stubGlobal("fetch",fetcher);
  render(<ProviderConfigurationPage providerKey="dataforseo"/>);
  fireEvent.click(await screen.findByRole("button",{name:"Configure collection"}));
  expect(screen.getByLabelText("Existing connection")).toHaveValue("connection-1");
  fireEvent.click(screen.getByRole("button",{name:"Continue"}));
  fireEvent.click(screen.getByRole("button",{name:"Continue"}));
  fireEvent.click(screen.getByLabelText("va loan calculator"));
  expect(screen.getByText("SERP collection — 1 selected")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"Continue"}));
  expect(screen.getByLabelText("Day")).toHaveValue("1");
  fireEvent.click(screen.getByRole("button",{name:"Continue"}));
  fireEvent.click(screen.getByRole("button",{name:"Preview collection plan"}));
  expect(await screen.findByRole("button",{name:"Activate Collection"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button",{name:"Save Disabled"}));
  await waitFor(()=>expect(fetcher.mock.calls.some(([,o])=>o?.method==="PUT")).toBe(true));
  const body=JSON.parse(fetcher.mock.calls.find(([,o])=>o?.method==="PUT")?.[1]?.body as string);
  expect(body.activate).toBe(false);expect(body.capabilities[0].target_ids).toEqual(["query-1"]);
  expect(fetcher.mock.calls.some(([u])=>u.includes("/run?"))).toBe(false);
});

it("keeps planned providers inspectable but not configurable",async()=>{
  vi.stubGlobal("fetch",vi.fn(()=>response({...configuration,detail:{...configuration.detail,implementation_status:"PLANNED"},capabilities:[]})));
  render(<ProviderConfigurationPage providerKey="semrush"/>);
  expect(await screen.findByText("Integration planned")).toBeInTheDocument();
  expect(screen.queryByRole("button",{name:"Configure collection"})).not.toBeInTheDocument();
  expect(screen.queryByRole("button",{name:"Preview manual run"})).not.toBeInTheDocument();
});

it("requires explicit scope before offering confirmation",async()=>{
  vi.stubGlobal("fetch",vi.fn((url:string)=>response(url.includes("/run?")?{choices:[],scope:[],fingerprint:"policy",requests:0,estimated_cost:null,blockers:["POLICY_DISABLED"],queued:0}:configuration)));
  render(<ProviderConfigurationPage providerKey="dataforseo"/>);
  fireEvent.click(await screen.findByRole("button",{name:"Preview manual run"}));
  expect(await screen.findByRole("button",{name:"Review selected collection"})).toBeDisabled();
  expect(screen.queryByRole("button",{name:"Confirm and queue collection"})).not.toBeInTheDocument();
});
