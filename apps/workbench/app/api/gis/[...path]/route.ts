import {NextRequest, NextResponse} from "next/server";

async function forward(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const {path} = await context.params;
  const base = process.env.GIS_API_BASE_URL ?? "http://localhost:8000";
  const target = new URL(`/${path.join("/")}`, base);
  target.search = request.nextUrl.search;
  const headers = new Headers({"Content-Type": "application/json", "X-GIS-Role": "ADMIN"});
  if (process.env.GIS_API_OPERATOR_KEY) headers.set("X-GIS-Operator-Key", process.env.GIS_API_OPERATOR_KEY);
  const body = request.method === "GET" ? undefined : await request.text();
  const response = await fetch(target, {method: request.method, headers, body, cache: "no-store"});
  return new NextResponse(await response.text(), {status: response.status, headers: {"Content-Type": response.headers.get("Content-Type") ?? "application/json"}});
}
export const GET = forward;
export const POST = forward;
