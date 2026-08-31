"use client";

import {useEffect, useState} from "react";
import {api, siteScope} from "@/lib/api";
import type {Overview} from "@/lib/types";
import {ErrorState, LoadingState, MetricCard, PageHeader} from "./ui";

export function OverviewPage() {
  const [data, setData] = useState<Overview>(); const [error, setError] = useState<string>();
  useEffect(() => { api<Overview>(`/api/v1/overview?${siteScope()}`).then(setData).catch((value: Error) => setError(value.message)); }, []);
  return <><PageHeader eyebrow="VAHomeMath · Growth intelligence" title="Decision overview" description="What needs attention, review, approval, measurement, or explanation right now."/>{error ? <ErrorState message={error}/> : !data ? <LoadingState/> : <><section className="metrics" aria-label="Work queues"><MetricCard label="Opportunities to review" value={data.opportunities_to_review} detail="Evidence-supported conditions"/><MetricCard label="Recommendations to review" value={data.recommendations_to_review} detail="Human decision required"/><MetricCard label="Interventions to approve" value={data.interventions_to_approve} detail="Separate approval boundary"/><MetricCard label="Active interventions" value={data.active_interventions} detail="Approved or underway"/><MetricCard label="Experiments running" value={data.experiments_running} detail="Measurement plans"/><MetricCard label="Observed outcomes" value={data.recent_outcomes} detail="Not causal impact"/></section><section className="notice"><strong>Governed workflow</strong><p>Recommendation acceptance creates a draft. Intervention approval is a separate operator decision, and approval still does not execute anything automatically.</p></section></>}</>;
}
