"use client";

import Link from "next/link";
import {useEffect, useState} from "react";
import {api, siteScope} from "@/lib/api";
import type {Opportunity, Page} from "@/lib/types";
import {EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge} from "./ui";

export function OpportunityInbox() {
  const [data, setData] = useState<Page<Opportunity>>(); const [error, setError] = useState<string>();
  useEffect(() => { api<Page<Opportunity>>(`/api/v1/opportunities?${siteScope()}&limit=25`).then(setData).catch((value: Error) => setError(value.message)); }, []);
  return <><PageHeader eyebrow="Review queue" title="Opportunity inbox" description="Evidence-supported conditions that warrant operator attention—not instructions to act."/>{error ? <ErrorState message={error}/> : !data ? <LoadingState/> : data.items.length === 0 ? <EmptyState title="No qualifying opportunities are currently supported by collected evidence." detail="Coverage may still be incomplete. Review Evidence and Collection for gaps or blockers."/> : <div className="tableWrap"><table><thead><tr><th>Opportunity</th><th>Priority</th><th>Evidence</th><th>Recommendation</th><th>Intervention</th></tr></thead><tbody>{data.items.map((item) => <tr key={item.id}><td><Link href={`/opportunities/${item.id}`}>{item.title}</Link><small>{item.entity_type} · {item.entity_key}</small></td><td><StatusBadge domain="priority">{item.priority}</StatusBadge></td><td>{item.evidence_sufficiency}</td><td>{item.recommendation_status ?? "—"}</td><td>{item.intervention_status ?? "—"}</td></tr>)}</tbody></table></div>}</>;
}
