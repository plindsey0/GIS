"use client";

import Link from "next/link";
import {useEffect, useState} from "react";
import {api, siteScope} from "../lib/api";
import {formatDate} from "../lib/format";
import {type Activity, duration, operationalLabel as label} from "../lib/operations";
import {AttemptTimeline, Cost, Disclosure, Summary} from "./operations";
import {ErrorState, LoadingState, PageHeader} from "./ui";

type Run = Activity & {
  ingestion_run: Record<string, unknown> | null;
  rights_policy: Record<string, unknown> | null;
  configuration: unknown;
  obligation: unknown;
  pipeline: {href: string; name: string};
  attempts: unknown;
};

export function OperationalRun({id}: {id: string}) {
  const [data, setData] = useState<Run>();
  const [error, setError] = useState<string>();
  useEffect(() => {
    api<Run>(`/api/v1/system/runs/${id}?${siteScope()}`)
      .then(setData)
      .catch((caught: Error) => setError(caught.message));
  }, [id]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState />;
  return (
    <>
      <nav className="subnav" aria-label="Run navigation">
        <Link href="/system/runs">Run history</Link>
        {data.provider_href && <Link href={data.provider_href}>Provider configuration</Link>}
        {data.target_href && <Link href={data.target_href}>Collection target</Link>}
        {data.source_href && <Link href={data.source_href}>Source data</Link>}
      </nav>
      <PageHeader eyebrow={label(data.outcome)} title={data.label} description={`${data.provider_name ?? "GIS processing"} · ${data.target_display_name}`} />
      <Summary items={[
        ["Capability", data.capability_name ?? "Not recorded"], ["Trigger", label(data.trigger)],
        ["Provider requests", data.request_count ?? "Not recorded"], ["Result", label(data.outcome)],
        ["Classification", label(data.effective_failure_category)], ["Errors", data.errors ?? (data.ingestion_run?.error_count as number) ?? "Unknown"],
        ["Timeliness", label(data.timeliness)], ["Due", formatDate(data.due_at)], ["Completed", formatDate(data.completed_at)],
        ["Attempts", data.attempt_count], ["Records received / inserted", `${data.records_received ?? "Unknown"} / ${data.records_inserted ?? "Unknown"}`],
        ["Provider cost", <Cost key="cost" item={data} />], ["Active execution time", duration(data.active_execution_duration)],
      ]} />
      {data.record_accounting_explanation && <p className="notice">{data.record_accounting_explanation}</p>}
      {data.state_interpretation && <p role="status">{data.state_interpretation} Recorded result: {label(data.recorded_status)}.</p>}
      {data.recovery_summary ? <p className="notice">{data.recovery_summary} Recovered {duration(data.recovery_latency)} late.</p> : data.failure_summary ? <p role="status">{label(data.failure_summary)}</p> : null}
      <Disclosure title="Execution and recovery">
        <Summary items={[
          ["Successful attempt duration", duration(data.successful_attempt_duration)], ["Total active execution", duration(data.active_execution_duration)],
          ["Obligation lateness", duration(data.obligation_lateness)], ["Recovery latency", duration(data.recovery_latency)],
          ["Wall-clock resolution (includes waiting)", duration(data.wall_clock_resolution_time)],
        ]} />
        <AttemptTimeline item={data} />
      </Disclosure>
      <Disclosure title="Data and ingestion">
        <Summary items={[
          ["Received", data.records_received], ["Inserted", data.records_inserted],
          ["Rejected", String(data.ingestion_run?.records_rejected ?? "Unknown")], ["Errors", String(data.ingestion_run?.error_count ?? "Unknown")],
        ]} />
        <Disclosure title="Raw ingestion metadata"><pre>{JSON.stringify(data.ingestion_run, null, 2)}</pre></Disclosure>
      </Disclosure>
      <Disclosure title="Governance and technical details">
        {data.rights_summary ? <Summary items={[
          ["Recorded rights policy", data.rights_summary.policy], ["Raw storage", label(data.rights_summary.raw_storage)],
          ["Derived analysis", label(data.rights_summary.derived_analysis)], ["Derived storage", label(data.rights_summary.derived_storage)],
        ]} /> : <p>No recorded rights policy. Unknown does not mean allowed.</p>}
        <p>These are recorded policy permissions, not a new rights approval.</p>
        <Link href={data.pipeline.href}>{data.pipeline.name} pipeline</Link>
        <Disclosure title="Full audit evidence"><pre>{JSON.stringify(data, null, 2)}</pre></Disclosure>
      </Disclosure>
    </>
  );
}
