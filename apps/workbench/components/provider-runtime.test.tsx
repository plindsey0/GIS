import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import {ProviderRuntime, RecoveryControl, scheduleLabel} from "./provider-runtime";

afterEach(()=>{cleanup();vi.unstubAllGlobals()});
it("formats recurrence in the business timezone, including daylight saving",()=>{
  expect(scheduleLabel("0 7 * * 4","America/New_York","2026-09-10T11:00:00Z")).toBe("Every Thursday at 7:00 AM EDT");
  expect(scheduleLabel("0 7 * * 4","America/New_York","2026-12-10T12:00:00Z")).toBe("Every Thursday at 7:00 AM EST");
});
it("keeps failed obligations and credential readiness visible",()=>{
  render(<ProviderRuntime providerKey="dataforseo" credential={{state:"CONNECTED_CREDENTIAL_UNAVAILABLE",reason:"Worker cannot resolve credential"}} obligations={[{id:"obligation",preferred_due_at:"2026-09-03T11:00:00Z",status:"FAILED",timeliness:"MISSED_UNSATISFIED",reason:"Needs attention",run:"/system/runs/original"}]}/>);
  expect(screen.getByText("Worker cannot resolve credential")).toBeInTheDocument();
  expect(screen.getByRole("link",{name:"Inspect original execution and attempts"})).toHaveAttribute("href","/system/runs/original");
});
it("does not permit confirmation of a blocked recovery",async()=>{
  const fetcher=vi.fn<(url:string,options?:RequestInit)=>Promise<Response>>(()=>Promise.resolve({ok:true,status:200,text:()=>Promise.resolve(JSON.stringify({fingerprint:"f",can_retry:false,blockers:["Paid execution is held"]}))} as Response));
  vi.stubGlobal("fetch",fetcher);
  render(<RecoveryControl providerKey="dataforseo" run="/system/runs/original"/>);
  fireEvent.click(screen.getByRole("button",{name:"Preview retry of failed obligation"}));
  expect(await screen.findByRole("button",{name:"Confirm paid recovery"})).toBeDisabled();
  expect(JSON.parse(fetcher.mock.calls[0]![1]!.body as string).confirmed).toBe(false);
});
