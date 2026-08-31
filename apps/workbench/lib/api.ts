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
  if (!response.ok) throw new WorkbenchApiError(response.status, await response.json() as ApiError);
  return response.json() as Promise<T>;
}
