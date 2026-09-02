import {afterEach, describe, expect, it, vi} from "vitest";
import {api, WorkbenchApiError} from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("Workbench API client", () => {
  it("returns a rich JSON response", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ok:true,status:200,text:async()=>JSON.stringify({items:[{label:"Evidence"}],total:1})})));
    await expect(api<{total:number}>("/api/v1/evidence/packages")).resolves.toMatchObject({total:1});
  });

  it("turns an unreadable upstream response into an actionable error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ok:false,status:502,text:async()=>"<html>wrong service</html>"})));
    await expect(api("/api/v1/overview")).rejects.toMatchObject({
      status: 502,
      payload: {
        error: {
          code: "INVALID_API_RESPONSE",
          message: "The GIS API proxy returned an unreadable response.",
          request_id: "workbench-proxy",
          details: null,
          retryable: true,
        },
      },
    } satisfies Partial<WorkbenchApiError>);
  });
});
