"use client";

import Link from "next/link";
import {useCallback, useEffect, useState} from "react";
import {api, siteScope} from "../lib/api";
import {formatDate, formatNumber, humanize} from "../lib/format";
import {ProviderRuntime,scheduleLabel,type CredentialReadiness,type Obligation} from "./provider-runtime";
import {ErrorState, LoadingState, PageHeader, StatusBadge} from "./ui";

type Policy = Record<string, string | number | boolean | null>;
type Capability = {
  key:string; name:string; description:string; enabled:boolean; target_ids:string[];
  choices:Array<{id:string;label:string;type:string;computed_status?:string;computed_cadence?:string;priority?:string;source?:string;blocker?:string;eligible?:boolean;unavailable_reason?:string}>; cadence:string;
  hour:number; minute:number; weekday:number; month_day:number; freshness_hours:number;
  per_run_limit:number; unit_price:string|null; pricing_notes:string;
  pricing_provenance:string; last_verified:string|null;
};
type Configuration = {
  detail:{credential_readiness?:CredentialReadiness|null;execution_readiness?:string;known_actual_cost_month?:string|null;known_reserved_cost_month?:string|null;cost_state?:string;request_count?:number;unknown_cost_requests?:number;name:string;description:string;implementation_status:string;connection_state:string;collection_state:string;blocking_reason:string|null;is_commercial:boolean;last_collection:string|null;next_collection:string|null;budget:{spent_day:string;spent_month:string};usage:Array<{id:string;status:string;requests:number;actual_cost:string|null;estimated_cost:string|null;occurred_at:string}>};
  policy:Policy; capabilities:Capability[];
  current_obligations?:Obligation[];latest_failed_attempt?:{at:string;category:string;reason:string;run_id:string}|null;
  connections:Array<{id:string;label:string;status:string}>;
  history:Array<{action:string;actor:string;at:string;reason:string|null}>;
  schedules:Array<{id:string;status:string;cron:string;timezone:string;next_at:string|null}>;
  recent_runs?:Array<{id:string;status:string;at:string}>;
};
type Preview={can_activate:boolean;blockers:string[];estimated_requests_month:string;estimated_cost_month:string|null;timezone:string;semantics:string;plans:Array<{key:string;targets:number;cadence:string;cron:string;estimated_requests_month:string;estimated_cost_month:string|null}>};
const steps=["Connection","Capabilities","Targets","Schedule","Budget & limits","Review & activate"];
const budgets=["daily_soft_budget","daily_hard_budget","monthly_soft_budget","monthly_hard_budget","per_run_hard_budget"];
const limits=["daily_request_limit","monthly_request_limit","per_run_request_limit"];

export function ProviderConfigurationPage({providerKey}:{providerKey:string}) {
  const [data,setData]=useState<Configuration>();
  const [policy,setPolicy]=useState<Policy>({});
  const [caps,setCaps]=useState<Capability[]>([]);
  const [step,setStep]=useState<number|null>(null);
  const [preview,setPreview]=useState<Preview>();
  const [error,setError]=useState<string>();
  const [message,setMessage]=useState<string>();
  const [search,setSearch]=useState("");
  const [busy,setBusy]=useState(false);
  const [authorizationReason,setAuthorizationReason]=useState("Reviewed provider configuration");
  const [runPreview,setRunPreview]=useState<{fingerprint:string;requests:number;estimated_cost:string|null;blockers:string[];queued:number}>();
  const [runRequestId,setRunRequestId]=useState("");
  const base=`/api/v1/providers/${providerKey}`;
  const load=useCallback(async()=>{
    try {
      const result=await api<Configuration>(`${base}/configuration?${siteScope()}`);
      setData(result);setPolicy(Object.fromEntries(Object.entries(result.policy).map(([key,value])=>[key,typeof value==="string"&&budgets.includes(key)?value.replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1"):value])));setCaps(result.capabilities.map(c=>({...c,unit_price:c.unit_price?.replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1")??null})));
    } catch(e) {setError((e as Error).message)}
  },[base]);
  useEffect(()=>{void load()},[load]);
  const updatePolicy=(key:string,value:string|number|boolean|null)=>{setPolicy(p=>({...p,[key]:value}));setPreview(undefined)};
  const updateCap=(key:string,update:Partial<Capability>)=>{setCaps(rows=>rows.map(c=>c.key===key?{...c,...update}:c));setPreview(undefined)};
  const payload=(activate=false)=>({policy:{...policy,actor:"workbench-admin",reason:authorizationReason},capabilities:caps,activate});
  async function review() {
    setBusy(true);setError(undefined);
    try {setPreview(await api<Preview>(`${base}/configuration/preview?${siteScope()}`,{method:"POST",body:JSON.stringify(payload())}));setStep(5)}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function save(activate:boolean) {
    setBusy(true);setError(undefined);
    try {await api(`${base}/configuration?${siteScope()}`,{method:"PUT",body:JSON.stringify(payload(activate))});setStep(null);setMessage(activate?"Collection activated under the reviewed policy. Future work will be reconciled by the existing orchestrator.":"Configuration saved disabled. No provider collection was authorized or queued.");await load()}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function action(action:string) {
    setBusy(true);setError(undefined);
    try {await api(`${base}/actions?${siteScope()}`,{method:"POST",body:JSON.stringify({action,actor:"workbench-admin",reason:"Operator provider control"})});setMessage("Policy and future orchestration work reconciled. Historical records are preserved.");await load()}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function run(confirmed=false) {
    setBusy(true);setError(undefined);
    const requestId=confirmed?runRequestId:crypto.randomUUID();
    try {
      const result=await api<NonNullable<typeof runPreview>>(`${base}/run?${siteScope()}`,{method:"POST",body:JSON.stringify({confirmed,request_id:requestId,fingerprint:runPreview?.fingerprint??""})});
      if(confirmed){setRunPreview(undefined);setMessage(`${result.queued} target executions queued. The orchestrator rechecks current policy before collection.`);await load()}
      else{setRunRequestId(requestId);setRunPreview(result)}
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  if(!data)return error?<ErrorState message={error}/>:<LoadingState/>;
  const d=data.detail, implemented=d.implementation_status==="IMPLEMENTED";
  return <>
    <PageHeader eyebrow="Data provider" title={d.name} description={d.description}/>
    <div className="providerToolbar"><Link href="/providers">All providers</Link><StatusBadge>{humanize(d.connection_state)}</StatusBadge><StatusBadge>{humanize(d.collection_state)}</StatusBadge>
      {implemented&&step===null&&<button onClick={()=>{setStep(0);setMessage(undefined)}}>Configure collection</button>}
      {implemented&&d.collection_state==="ACTIVE"&&<><button className="secondaryButton" disabled={busy} onClick={()=>void action("PAUSE")}>Emergency pause</button><button className="secondaryButton" disabled={busy} onClick={()=>void action("DISABLE")}>Disable collection</button></>}
      {implemented&&d.collection_state==="PAUSED"&&<button disabled={busy} onClick={()=>void action("RESUME")}>Resume existing policy</button>}
    </div>
    {error&&<ErrorState message={error}/>} {message&&<p role="status" className="providerNotice">{message}</p>}
    {implemented&&step===null&&<button className="secondaryButton" disabled={busy} onClick={()=>void run()}>Preview manual run</button>}
    {runPreview&&<section className="providerSection" aria-label="Manual run preview"><h2>Confirm manual collection</h2><p>{runPreview.requests} target requests · Estimated cost: {runPreview.estimated_cost===null?"Unknown":`$${runPreview.estimated_cost}`}</p><p>Confirmation queues work under the current policy. It does not bypass budgets, rights or disabled targets.</p>{runPreview.blockers.map(b=><p role="alert" key={b}>{humanize(b)}</p>)}<div className="providerToolbar"><button className="secondaryButton" onClick={()=>setRunPreview(undefined)}>Cancel run</button><button disabled={busy||runPreview.blockers.length>0} onClick={()=>void run(true)}>Confirm and queue collection</button></div></section>}
    {!implemented?<section className="recordCard"><h2>Integration planned</h2><p>This provider remains inspectable, but activation is unavailable until an executable adapter is implemented. No schedule or budget changes are offered.</p></section>:null}
    {step===null?<>
      <section className="providerSection"><h2>Operational status</h2><dl className="detailGrid"><div><dt>Implementation</dt><dd>{humanize(d.implementation_status)}</dd></div><div><dt>Last successful collection</dt><dd>{formatDate(d.last_collection)}</dd></div><div><dt>Next recurrence (not proof of completion)</dt><dd>{d.next_collection?formatDate(d.next_collection):"Not scheduled"}</dd></div><div><dt>Collection authorization</dt><dd>{humanize(d.collection_state)}</dd></div><div><dt>Execution readiness</dt><dd>{humanize(d.execution_readiness??"UNKNOWN")}</dd></div></dl></section>
      <ProviderRuntime providerKey={providerKey} credential={d.credential_readiness} obligations={data.current_obligations} failed={data.latest_failed_attempt}/>
      <section className="providerSection"><h2>Configuration summary</h2><div className="providerGrid">{caps.map(c=><article className="recordCard providerCapability" key={c.key}><StatusBadge>{c.enabled?"Enabled":"Disabled"}</StatusBadge><h3>{c.name}</h3><p>{c.description}</p><p>{c.target_ids.length} authorized targets · Configured cadence: {humanize(c.cadence)}</p><ul>{c.choices.filter(t=>c.target_ids.includes(t.id)).map(t=><li key={t.id}>{t.label}{t.computed_cadence&&<small>GIS recommendation: {humanize(t.computed_cadence)} · Provider override: Yes</small>}</li>)}</ul><p>Freshness: {c.freshness_hours%24===0?`${c.freshness_hours/24} days`:`${c.freshness_hours} hours`}</p>{d.is_commercial&&<><p>Pricing: {c.unit_price===null?"Not configured":`${new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",minimumFractionDigits:2,maximumFractionDigits:8}).format(Number(c.unit_price))} per target request`}</p><p>Pricing source: {c.pricing_provenance==="USER_CONFIGURED"?"Operator-entered / user-managed":humanize(c.pricing_provenance)}</p><p>Last verified: {formatDate(c.last_verified)}</p>{c.pricing_notes&&<p>{c.pricing_notes}</p>}</>}</article>)}</div></section>
      <section className="providerSection"><h2>Execution policy</h2>{data.schedules.length===0?<p>No derived execution schedule yet.</p>:data.schedules.map(s=><div key={s.id}><p>{humanize(s.status)} · {scheduleLabel(s.cron,s.timezone,s.next_at)}</p><p>Next recurrence: {s.next_at?formatDate(s.next_at):"Not scheduled"}</p><details><summary>Technical schedule</summary>{s.cron} ({s.timezone})</details></div>)}</section>
      {d.is_commercial&&<section className="providerSection"><h2>Budget and request limits</h2><div className="providerFields"><div>{budgets.map(key=><p key={key}>{humanize(key)}: {policy[key]==null?"Not configured":formatNumber(policy[key],"currency")}</p>)}</div><div><p>Daily requests: {policy.daily_request_limit??"Not configured"}</p><p>Monthly requests: {policy.monthly_request_limit??"Not configured"}</p><p>Per-execution requests: {policy.per_run_request_limit??"Not configured"}</p><p>Unknown cost: {policy.allow_unknown_cost?"Explicitly permitted within request limits":"Blocked"}</p></div></div></section>}
      <section className="providerSection"><h2>Usage</h2><p>Requests this business month: {d.request_count??0} · Cost state: {humanize(d.cost_state??"NO_USAGE")}</p>{d.unknown_cost_requests? <p>{d.unknown_cost_requests} requests have unknown/unreconciled cost. Known totals below are not complete spend.</p>:null}<p>Known actual cost this month: {d.known_actual_cost_month==null?"Not recorded":formatNumber(d.known_actual_cost_month,"currency")} · Known reserved cost: {d.known_reserved_cost_month==null?"None recorded":formatNumber(d.known_reserved_cost_month,"currency")}</p><p>Known/estimated recorded subtotal today: {formatNumber(d.budget.spent_day,"currency")} · Month: {formatNumber(d.budget.spent_month,"currency")}</p>{d.usage.length===0?<p>No control-plane usage recorded. This is not a statement that future calls are free.</p>:<ul>{d.usage.map(u=><li key={u.id}>{formatDate(u.occurred_at)} · {u.requests} requests · {humanize(u.status)} · Actual cost: {u.actual_cost===null?"Unknown / unreconciled":formatNumber(u.actual_cost,"currency")}</li>)}</ul>}</section>
      <section className="providerSection"><h2>Recent executions</h2>{data.recent_runs?.length?<ul>{data.recent_runs.map(r=><li key={r.id}><Link href={`/system/runs/${r.id}`}>{formatDate(r.at)} · {humanize(r.status)}</Link></li>)}</ul>:<p>No orchestration history for this connection yet.</p>}<Link href="/system/pipelines">Inspect live pipelines</Link>{" · "}<Link href="/system/sources">Inspect sources and rights</Link></section>
      <section className="providerSection"><h2>Configuration history</h2>{data.history.length===0?<p>No configuration changes yet.</p>:<ul>{data.history.map((h,i)=><li key={i}>{formatDate(h.at)} · {humanize(h.action)} · {h.actor}{h.reason?` — ${h.reason}`:""}</li>)}</ul>}</section>
    </>:<section className="providerWizard" aria-label="Collection configuration">
      <ol className="providerSteps">{steps.map((s,i)=><li key={s} aria-current={step===i?"step":undefined}>{s}</li>)}</ol>
      <h2>{steps[step]}</h2>
      {step===0&&<><p>Connection metadata identifies the credential reference; it does not prove runtime authentication. Connecting does not authorize collection or spending.</p>{d.credential_readiness&&<p>Saved connection readiness: {humanize(d.credential_readiness.state)}. {d.credential_readiness.reason}</p>}<label>Existing connection<select value={String(policy.data_source_connection_id??"")} onChange={e=>updatePolicy("data_source_connection_id",e.target.value||null)}><option value="">Select a connection</option>{data.connections.map(c=><option key={c.id} value={c.id}>{c.label} — {humanize(c.status)}</option>)}</select></label>{data.connections.length===0&&<p>No existing connection is available. You may inspect configuration, but activation is blocked.</p>}</>}
      {step===1&&<div className="providerGrid">{caps.map(c=><label className="recordCard providerCapability" key={c.key}><span><input type="checkbox" checked={c.enabled} onChange={e=>updateCap(c.key,{enabled:e.target.checked})}/> {c.name}</span><p>{c.description}</p><small>{d.is_commercial?"Commercial API usage":"No commercial dollar budget required"}</small></label>)}</div>}
      {step===2&&<><p>Select to authorize for this provider when you save. GIS computed recommendations are preserved. Discovery alone does not authorize spending.</p><label>Authorization reason<input value={authorizationReason} onChange={e=>setAuthorizationReason(e.target.value)}/></label><label>Find targets<input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search query or domain"/></label>{caps.filter(c=>c.enabled).map(c=><fieldset key={c.key}><legend>{c.name} — {c.target_ids.length} selected</legend><div className="providerTargets">{c.choices.filter(t=>t.label.toLowerCase().includes(search.toLowerCase())).map(t=><div key={t.id}><label><input type="checkbox" aria-label={t.label} disabled={t.eligible===false&&!c.target_ids.includes(t.id)} checked={c.target_ids.includes(t.id)} onChange={e=>updateCap(c.key,{target_ids:e.target.checked?[...c.target_ids,t.id]:c.target_ids.filter(id=>id!==t.id)})}/>{t.label} — {c.target_ids.includes(t.id)?"Provider authorized (on save)":"Authorize for this provider"}</label><small>{humanize(t.computed_status??"TRACKED")} · {humanize(t.source??"GIS canonical registry")} · Priority: {humanize(t.priority??"UNKNOWN")} · GIS recommended cadence: {humanize(t.computed_cadence??"UNKNOWN")} · Current blocker: {humanize(t.blocker??"NONE")}</small><small>Configured provider cadence: {humanize(c.cadence)}. {t.unavailable_reason??"An explicit provider override does not change the computed recommendation."}</small></div>)}</div>{c.choices.length===0&&<p>No canonical targets are available for this capability.</p>}<button className="secondaryButton" onClick={()=>updateCap(c.key,{target_ids:[]})}>Clear selection</button></fieldset>)}</>}
      {step===3&&<><label>Business timezone<input value={String(policy.timezone??"UTC")} onChange={e=>updatePolicy("timezone",e.target.value)}/></label>{providerKey==="google_pagespeed"&&<p>LAB and FIELD share one request. Select matching targets and schedules to avoid duplicate retrievals.</p>}{caps.filter(c=>c.enabled).map(c=><fieldset key={c.key}><legend>{c.name}</legend><div className="providerFields"><label>Cadence<select value={c.cadence} onChange={e=>updateCap(c.key,{cadence:e.target.value})}>{["MANUAL_ONLY","DAILY","WEEKLY","MONTHLY"].map(v=><option key={v} value={v}>{humanize(v)}</option>)}</select></label><label>Hour (24-hour)<input type="number" min="0" max="23" value={c.hour} onChange={e=>updateCap(c.key,{hour:Number(e.target.value)})}/></label><label>Minute<input type="number" min="0" max="59" value={c.minute} onChange={e=>updateCap(c.key,{minute:Number(e.target.value)})}/></label>{c.cadence==="WEEKLY"&&<label>Day<select value={c.weekday} onChange={e=>updateCap(c.key,{weekday:Number(e.target.value)})}>{["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"].map((v,i)=><option key={v} value={i}>{v}</option>)}</select></label>}{c.cadence==="MONTHLY"&&<label>Day of month (1–28)<input type="number" min="1" max="28" value={c.month_day} onChange={e=>updateCap(c.key,{month_day:Number(e.target.value)})}/></label>}<label>Freshness target (hours)<input type="number" min="1" value={c.freshness_hours} onChange={e=>updateCap(c.key,{freshness_hours:Number(e.target.value)})}/></label></div></fieldset>)}<p>Missed or transiently failed collections may retry within bounded limits. Paid schedules do not replay every missed occurrence.</p></>}
      {step===4&&<>{d.is_commercial?<><p>Soft budgets warn. Hard budgets block known excess spend. Per-run ceilings apply to one target execution. Monetary values are enforced as decimals in USD.</p><div className="providerFields">{budgets.map(key=><label key={key}>{humanize(key)} (USD)<input inputMode="decimal" value={String(policy[key]??"")} placeholder="Not configured" onChange={e=>updatePolicy(key,e.target.value||null)}/></label>)}{limits.map(key=><label key={key}>{humanize(key)}<input type="number" min="1" value={String(policy[key]??"")} onChange={e=>updatePolicy(key,e.target.value?Number(e.target.value):null)}/></label>)}</div><label><input type="checkbox" checked={Boolean(policy.allow_unknown_cost)} onChange={e=>updatePolicy("allow_unknown_cost",e.target.checked)}/>Explicitly permit unknown cost only within bounded request limits</label>{caps.filter(c=>c.enabled).map(c=><fieldset key={c.key}><legend>{c.name} pricing assumption</legend><p>One unit represents one target retrieval. GIS does not discover or invent provider prices.</p><label>USD per target request<input inputMode="decimal" value={c.unit_price??""} placeholder="Unknown" onChange={e=>updateCap(c.key,{unit_price:e.target.value||null})}/></label><label>Pricing provenance notes<input value={c.pricing_notes} onChange={e=>updateCap(c.key,{pricing_notes:e.target.value})}/></label><p>Last verified: {formatDate(c.last_verified)}</p></fieldset>)}</>:<p>Dollar budgets are not applicable to this free provider.</p>}{caps.filter(c=>c.enabled).map(c=><label key={c.key}>{c.name}: maximum authorized targets (1–100)<input type="number" min="1" max="100" value={c.per_run_limit} onChange={e=>updateCap(c.key,{per_run_limit:Number(e.target.value)})}/></label>)}</>}
      {step===5&&preview&&<><h3>{d.is_commercial?"Review commercial collection authorization":"Review collection policy"}</h3><p>Estimated monthly target requests: {preview.estimated_requests_month}</p><p>Estimated monthly cost: {preview.estimated_cost_month===null?"Unknown":`$${preview.estimated_cost_month}`}</p><p>Monthly hard budget: {policy.monthly_hard_budget?`$${policy.monthly_hard_budget}`:"Not configured"} · Per-run hard budget: {policy.per_run_hard_budget?`$${policy.per_run_hard_budget}`:"Not configured"}</p>{preview.plans.map(p=><p key={p.key}>{humanize(p.key)}: {p.targets} targets · {humanize(p.cadence)} · {p.cron} ({preview.timezone})</p>)}<small>{preview.semantics}</small>{preview.blockers.length>0&&<div role="alert"><h3>Activation blockers</h3><ul>{preview.blockers.map(b=><li key={b}>{b}</li>)}</ul></div>}<p>Saving disabled makes no provider call and creates no runnable work. Activation authorizes future execution within these limits.</p></>}
      <div className="providerToolbar"><button className="secondaryButton" disabled={busy} onClick={()=>{setStep(null);void load()}}>Cancel</button>{step>0&&<button className="secondaryButton" disabled={busy} onClick={()=>setStep(step-1)}>Back</button>}{step<4&&<button onClick={()=>setStep(step+1)}>Continue</button>}{step===4&&<button disabled={busy} onClick={()=>void review()}>Preview collection plan</button>}{step===5&&<><button className="secondaryButton" disabled={busy} onClick={()=>void save(false)}>Save Disabled</button><button disabled={busy||!preview?.can_activate} onClick={()=>void save(true)}>Activate Collection</button></>}</div>
    </section>}
  </>;
}
