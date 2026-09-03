"use client";
import Link from "next/link";
import {useState} from "react";
import {api,siteScope} from "../lib/api";
import {formatDate,humanize} from "../lib/format";

export type CredentialReadiness={state:string;reason:string;worker_verified?:boolean;execution_held?:boolean;authentication_state?:string;last_authentication_success_at?:string|null;last_authentication_failure_at?:string|null};
export type Obligation={id:string;preferred_due_at:string;status:string;timeliness:string;reason:string;run:string|null};
type RetryPreview={fingerprint:string;blockers:string[];can_retry:boolean};
export function RecoveryControl({providerKey,run}:{providerKey:string;run:string}){
  const [preview,setPreview]=useState<RetryPreview>();const [error,setError]=useState("");const [queued,setQueued]=useState(false);const [busy,setBusy]=useState(false);
  async function request(confirmed=false){setBusy(true);setError("");try{const response=await api<RetryPreview>(`/api/v1/providers/${providerKey}/recover/${run.split("/").pop()}?${siteScope()}`,{method:"POST",body:JSON.stringify({confirmed,fingerprint:preview?.fingerprint??"",request_id:crypto.randomUUID()})});if(confirmed){setQueued(true);setPreview(undefined)}else setPreview(response)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  return <div>{queued?<p role="status">Recovery queued against the original obligation. Prior attempts remain in history.</p>:<button className="secondaryButton" disabled={busy} onClick={()=>void request()}>Preview retry of failed obligation</button>}{error&&<p role="alert">{error}</p>}{preview&&<div role="dialog" aria-label="Confirm obligation recovery"><p>Retry the original obligation with current rights, credential and budget checks. This can consume paid credits.</p>{preview.blockers.map(b=><p key={b} role="alert">{b}</p>)}<button className="secondaryButton" onClick={()=>setPreview(undefined)}>Cancel recovery</button><button disabled={busy||!preview.can_retry} onClick={()=>void request(true)}>Confirm paid recovery</button></div>}</div>
}
export function ProviderRuntime({providerKey,credential,obligations=[],failed}:{providerKey:string;credential?:CredentialReadiness|null;obligations?:Obligation[];failed?:{at:string;category:string;reason:string;run_id:string}|null}){
  return <section className="providerSection"><h2>Execution readiness and current obligations</h2>{credential&&<><p>Credential readiness: <strong>{humanize(credential.state)}</strong></p><p>{credential.reason}</p><p>Credential resolution is not proof of provider authentication or permission to spend.</p></>}{obligations.length===0?<p>No current overdue obligation recorded.</p>:obligations.map(o=><article key={o.id}><h3>Due {formatDate(o.preferred_due_at)}</h3><p>{humanize(o.status)} · {humanize(o.timeliness)}</p><p>{o.reason}</p>{o.run&&<><Link href={o.run}>Inspect original execution and attempts</Link>{["FAILED","BLOCKED"].includes(o.status)&&<RecoveryControl providerKey={providerKey} run={o.run}/>}</>}</article>)}{failed&&<p>Latest failed attempt: <Link href={`/system/runs/${failed.run_id}`}>{formatDate(failed.at)}</Link> · {humanize(failed.category??"UNKNOWN")} · {failed.reason}</p>}</section>
}
export function scheduleLabel(cron:string,timezone:string,next:string|null):string{
  const [minute,hour,day,,weekday]=cron.split(" ");
  if(!/^\d+$/.test(minute??"")||!/^\d+$/.test(hour??""))return "Custom schedule";
  const h=Number(hour),time=`${h%12||12}:${minute.padStart(2,"0")} ${h<12?"AM":"PM"}`;
  const zone=new Intl.DateTimeFormat("en-US",{timeZone:timezone,timeZoneName:"short"}).formatToParts(next?new Date(next):new Date()).find(p=>p.type==="timeZoneName")?.value??timezone;
  return `${weekday!=="*"?`Every ${["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"][Number(weekday)]}`:day!=="*"?`Monthly on day ${day}`:"Every day"} at ${time} ${zone}`;
}
