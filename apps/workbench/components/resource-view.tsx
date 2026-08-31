"use client";

import {useEffect, useState} from "react";
import {api, siteScope} from "@/lib/api";
import type {Page, Resource} from "@/lib/types";
import {EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge} from "./ui";

type Item = Record<string, unknown>;
const copy: Record<string, {title: string; description: string; empty: string}> = {
  recommendations: {title: "Recommendations", description: "Governed intervention candidates awaiting human judgment.", empty: "No evidence-supported recommendations are currently ready for review."},
  interventions: {title: "Interventions", description: "Explicitly governed work from draft through measurement.", empty: "No intervention drafts or active interventions are currently recorded."},
  evidence: {title: "Evidence", description: "Evidence packages, quality, conflicts, gaps, rights and provenance.", empty: "No evidence packages have been produced for this site yet."},
  markets: {title: "Market", description: "The explicitly defined observable digital market.", empty: "No market definition is currently available for this site."},
  collection: {title: "Collection", description: "Targets, evidence gaps, collectors, cost and disabled schedule state.", empty: "No collection targets are currently proposed or active."},
  experiments: {title: "Experiments", description: "Foundational measurement plans without implied causal impact.", empty: "No experiments are currently registered."},
  outcomes: {title: "Outcomes", description: "Observed change, clearly separated from causal impact.", empty: "No observed outcomes are currently available."}
};

export function ResourceList({kind}: {kind: keyof typeof copy}) {
  const [data, setData] = useState<Page<Item> | null>(null); const [error, setError] = useState<string>();
  useEffect(() => { const path = kind === "evidence" ? "evidence/packages" : kind; api<Page<Item>>(`/api/v1/${path}?${siteScope()}`).then(setData).catch((value: Error) => setError(value.message)); }, [kind]);
  const labels = copy[kind];
  return <><PageHeader eyebrow="Intelligence workbench" title={labels.title} description={labels.description}/>{error ? <ErrorState message={error}/> : !data ? <LoadingState/> : data.items.length === 0 ? <EmptyState title={labels.empty} detail="GIS preserves missing and insufficient states; this does not mean the underlying condition is zero or resolved."/> : <><p className="muted">Showing {data.items.length} of {data.total} governed records.</p><div className="tableWrap"><table><thead><tr><th>Resource</th><th>Status</th><th>Updated</th></tr></thead><tbody>{data.items.map((item) => <tr key={String(item.id)}><td>{String(item.display_value ?? item.normalized_identity ?? item.name ?? item.title ?? item.id)}</td><td><StatusBadge>{String(item.status ?? item.state ?? "Unknown")}</StatusBadge></td><td>{String(item.updated_at ?? item.created_at ?? "—")}</td></tr>)}</tbody></table></div></>}</>;
}

export function ResourceDetail({kind, id}: {kind: string; id: string}) {
  const [data, setData] = useState<Resource>(); const [error, setError] = useState<string>();
  useEffect(() => { const path = kind === "evidence" ? "evidence/packages" : kind; api<Resource>(`/api/v1/${path}/${id}?${siteScope()}`).then(setData).catch((value: Error) => setError(value.message)); }, [kind, id]);
  const collections = data ? Object.entries(data.data).filter(([, value]) => Array.isArray(value)) as [string, Item[]][] : [];
  return <><PageHeader eyebrow={`${kind} detail`} title={data ? String(data.data.title ?? data.data.name ?? data.id) : "Loading detail"} description="A bounded operational view over authoritative GIS domain state."/>{error ? <ErrorState message={error}/> : !data ? <LoadingState/> : <><dl className="detailGrid">{Object.entries(data.data).filter(([, value]) => typeof value !== "object").map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value === null ? "Unknown" : String(value)}</dd></div>)}</dl>{collections.map(([key, items]) => <section className="detailCollection" key={key}><h2>{key.replaceAll("_", " ")}</h2>{items.length === 0 ? <p className="muted">No records are currently available.</p> : <div className="cardGrid">{items.map((item, index) => <article className="card" key={String(item.id ?? index)}><h3>{String(item.title ?? item.name ?? item.event_type ?? item.id ?? `${key} ${index + 1}`)}</h3><StatusBadge>{String(item.status ?? item.state ?? item.decision ?? "Recorded")}</StatusBadge><p>{String(item.summary ?? item.description ?? item.rationale ?? "Authoritative GIS record")}</p></article>)}</div>}</section>)}</>}</>;
}
