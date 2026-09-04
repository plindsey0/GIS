import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {SourceGovernance} from "./source-governance";

const source={label:"BuiltWith",description:"Governed technology source",impact:{explanation:"No materialized asset lineage registered",pipeline_links:[{pipeline:"builtwith_technology",href:"/system/pipelines/builtwith_technology"}]},connections:[{id:"connection",status:"ACTIVE",required_rights:[{label:"Raw storage",status:"UNKNOWN",blocking:true},{label:"Derived storage",status:"ALLOWED",blocking:false}],credential_readiness:{execution_held:true,authentication_state:"NOT_INDEPENDENTLY_VALIDATED"},account_telemetry:{state:"UNKNOWN",checked_at:null,values:{},failure_category:null}}]};
const review={policy:{id:"old",policy_version:"1"},decisions:{raw_storage_allowed:"UNKNOWN"},grants:{raw_retention:"UNKNOWN",normalized_retention:"UNKNOWN",ai_training:"UNKNOWN"},history:[{id:"old",policy_version:"1"}]};
function response(value:unknown){return Promise.resolve({ok:true,status:200,text:async()=>JSON.stringify(value)} as Response)}
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()});
it("remains readable before the existing API is restarted after deployment",async()=>{
 vi.stubGlobal("fetch",vi.fn(()=>response({...source,impact:{unmapped_dependencies:true},connections:[{id:"connection",status:"ACTIVE"}]})));
 render(<SourceGovernance sourceKey="builtwith"/>);
 expect(await screen.findByText("Restart GIS after deployment to load detailed governance and dependency diagnostics.")).toBeVisible();
});
it("shows precise rights and unknown account state without automatic requests",async()=>{
 const fetcher=vi.fn(()=>response(source));vi.stubGlobal("fetch",fetcher);
 render(<SourceGovernance sourceKey="builtwith"/>);
 expect(await screen.findByText("Raw storage: UNKNOWN — ALLOWED required; blocking")).toBeVisible();
 expect(screen.getByText("Never retrieved. Unknown is not zero.")).toBeVisible();
 expect(fetcher).toHaveBeenCalledTimes(1);
 expect(screen.getByRole("link",{name:/builtwith technology/i})).toHaveAttribute("href","/system/pipelines/builtwith_technology");
});
it("submits a versioned review only after explicit approval and keeps unrelated grants unknown",async()=>{
 const fetcher=vi.fn((url:string)=>response(url.includes("/rights")?review:source));vi.stubGlobal("fetch",fetcher);vi.spyOn(window,"confirm").mockReturnValue(true);
 render(<SourceGovernance sourceKey="builtwith"/>);fireEvent.click(await screen.findByText("Review rights"));
 fireEvent.change(await screen.findByLabelText(/raw retention/i),{target:{value:"ALLOWED"}});
 fireEvent.change(screen.getByLabelText(/review authority/i),{target:{value:"Operator"}});
 fireEvent.change(screen.getByLabelText(/^policy version$/i),{target:{value:"2"}});
 fireEvent.change(screen.getByLabelText(/documented basis/i),{target:{value:"Reviewed agreement"}});
 fireEvent.click(screen.getByText("Approve new policy version"));
 await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>url.includes("/reviews?"))).toBe(true));
 expect(screen.getByLabelText(/ai training/i)).toHaveValue("UNKNOWN");
});
it("cancelling telemetry confirmation makes no account call",async()=>{
 const fetcher=vi.fn(()=>response(source));vi.stubGlobal("fetch",fetcher);vi.spyOn(window,"confirm").mockReturnValue(false);
 render(<SourceGovernance sourceKey="builtwith"/>);fireEvent.click(await screen.findByText("Refresh account telemetry"));
 expect(fetcher).toHaveBeenCalledTimes(1);
});
