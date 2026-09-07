"use client";

import Link from "next/link";
import {useEffect, useState} from "react";
import {api, siteScope} from "@/lib/api";
import type {Opportunity, Page} from "@/lib/types";
import {EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge} from "./ui";

export function OpportunityInbox() {
  const [data, setData] = useState<Page<Opportunity>>(); const [error, setError] = useState<string>();
  useEffect(() => { api<Page<Opportunity>>(`/api/v1/opportunities?${siteScope()}&limit=25`).then(setData).catch((value: Error) => setError(value.message)); }, []);
  return <><PageHeader eyebrow="Review queue" title="Opportunity inbox" description="Evidence-grounded opportunities move through explicit human review before recommendations or experiment proposals can exist."/>{error ? <ErrorState message={error}/> : !data ? <LoadingState/> : data.items.length === 0 ? <EmptyState title="No evidence package currently satisfies a complete opportunity detector." detail="This is a valid result. No threshold or trust boundary is weakened to fill the queue."/> : <div className="tableWrap"><table><thead><tr><th>Opportunity</th><th>Priority</th><th>Evidence</th><th>Human review</th><th>Recommendation</th><th>Proposal</th></tr></thead><tbody>{data.items.map((item) => <tr key={item.id}><td><Link href={`/opportunities/${item.id}`}>{item.title}</Link><small>{item.entity_type} · {item.entity_key}{item.governed_intelligence?" · model-inferred":" · deterministic"}</small></td><td><StatusBadge domain="priority">{item.priority}</StatusBadge></td><td>{item.evidence_sufficiency}</td><td>{item.review_state ?? "Not reviewed"}</td><td>{item.recommendation_state ?? "Not generated"}</td><td>{item.experiment_state ?? "Not proposed"}</td></tr>)}</tbody></table></div>}</>;
}
