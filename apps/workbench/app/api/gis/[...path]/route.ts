import {NextRequest, NextResponse} from "next/server";

async function forward(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const {path} = await context.params;
  // Use the same explicit IPv4 loopback address that gis-api binds to. On
  // machines where localhost resolves to ::1 first, another service can own
  // the IPv6 side of port 8000 and return an unrelated HTML response.
  const base = process.env.GIS_API_BASE_URL ?? "http://127.0.0.1:8001";
  try {
    const target = new URL(`/${path.join("/")}`, base);
    target.search = request.nextUrl.search;
    const headers = new Headers({"Content-Type": "application/json", "X-GIS-Role": "ADMIN"});
    if (process.env.GIS_API_OPERATOR_KEY) headers.set("X-GIS-Operator-Key", process.env.GIS_API_OPERATOR_KEY);
    const body = request.method === "GET" ? undefined : await request.text();
    const response = await fetch(target, {method: request.method, headers, body, cache: "no-store", signal: AbortSignal.timeout(10_000)});
    const text = await response.text();
    let payload: unknown;
    try { payload = JSON.parse(text); }
    catch {
      payload = {
        error: {
          code: "GIS_UPSTREAM_ERROR",
          message: response.ok
            ? "The GIS API returned an unreadable response."
            : "The GIS API could not complete this request.",
          request_id: response.headers.get("X-Request-ID") ?? "workbench-proxy",
          details: null,
          retryable: response.status >= 500,
        },
      };
    }
    return NextResponse.json(payload, {status: response.status});
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "GIS_UPSTREAM_UNAVAILABLE",
          message: "The GIS API did not respond on the configured local endpoint within 10 seconds.",
          request_id: "workbench-proxy",
          details: null,
          retryable: true,
        },
      },
      {status: 502},
    );
  }
}
export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const dynamic = "force-dynamic";
