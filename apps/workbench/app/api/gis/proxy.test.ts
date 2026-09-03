import {afterEach, describe, expect, it, vi} from "vitest";
import {NextRequest} from "next/server";
import {GET} from "./[...path]/route";

afterEach(() => vi.unstubAllGlobals());

describe("GIS API proxy", () => {
  it("normalizes a plain-text upstream 500 to the GIS error contract", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("Internal Server Error", {
      status: 500,
      headers: {"Content-Type": "text/plain", "X-Request-ID": "upstream-request"},
    })));
    const request = new NextRequest("http://localhost/api/gis/api/v1/providers");
    const response = await GET(request, {params: Promise.resolve({path:["api", "v1", "providers"]})});
    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      error: {
        code: "GIS_UPSTREAM_ERROR",
        message: "The GIS API could not complete this request.",
        request_id: "upstream-request",
        details: null,
        retryable: true,
      },
    });
  });

  it("preserves a structured upstream API error", async () => {
    const upstream = {error:{code:"REQUEST_INVALID",message:"Bad scope",request_id:"r",details:null,retryable:false}};
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(upstream, {status:422})));
    const request = new NextRequest("http://localhost/api/gis/api/v1/providers");
    const response = await GET(request, {params: Promise.resolve({path:["api", "v1", "providers"]})});
    expect(response.status).toBe(422);
    await expect(response.json()).resolves.toEqual(upstream);
  });
});
