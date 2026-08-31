"use client";

import {useEffect, useState} from "react";
import {api, siteScope} from "@/lib/api";
import {EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge} from "./ui";

type Capability = {items: {schedule: string; status: string; latest_success: string | null; stale_since: string | null; reason: string | null}[]; fixture_ai_provider: boolean; production_ai_operational: boolean};
export function SystemPage() {
  const [data, setData] = useState<Capability>(); const [error, setError] = useState<string>();
  useEffect(() => { api<Capability>(`/api/v1/capabilities?${siteScope()}`).then(setData).catch((value: Error) => setError(value.message)); }, []);
  return <><PageHeader eyebrow="Operations" title="System & capabilities" description="Why GIS is—or is not—able to produce a current answer."/>{error ? <ErrorState message={error}/> : !data ? <LoadingState/> : <><div className="notice"><strong>AI provider</strong><p>{data.fixture_ai_provider ? "Fixture / development recommendation provider" : "Not configured"}. Production AI operational: {data.production_ai_operational ? "Yes" : "No"}.</p></div>{data.items.length === 0 ? <EmptyState title="No schedules are configured." detail="Capabilities may be implemented without an operational collection schedule."/> : <div className="tableWrap"><table><thead><tr><th>Pipeline</th><th>Schedule</th><th>Latest success</th><th>Stale since</th><th>Operational note</th></tr></thead><tbody>{data.items.map((item) => <tr key={item.schedule}><td>{item.schedule}</td><td><StatusBadge>{item.status}</StatusBadge></td><td>{item.latest_success ?? "Unknown"}</td><td>{item.stale_since ?? "—"}</td><td>{item.reason ?? "—"}</td></tr>)}</tbody></table></div>}</>}</>;
}
