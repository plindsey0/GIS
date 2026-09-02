import type {ApiError} from "./types";

const baseUrl = "/api/gis";

export class WorkbenchApiError extends Error {
  constructor(public status: number, public payload: ApiError) { super(payload.error.message); }
}

export function siteScope(): URLSearchParams {
  const tenant = process.env.NEXT_PUBLIC_GIS_TENANT_ID ?? "";
  const site = process.env.NEXT_PUBLIC_GIS_WORKBENCH_SITE_ID ?? "";
  return new URLSearchParams({tenant_id: tenant, site_id: site});
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  const response = await fetch(`${baseUrl}${path}`, {...init, headers, cache: "no-store"});
  const text = await response.text();
  let payload: unknown;
  try { payload = JSON.parse(text); }
  catch { throw new WorkbenchApiError(response.status, {error:{code:"INVALID_API_RESPONSE",message:"The GIS API proxy returned an unreadable response.",request_id:"workbench-proxy",details:null,retryable:true}}); }
  if (!response.ok) throw new WorkbenchApiError(response.status, payload as ApiError);
  return payload as T;
}
