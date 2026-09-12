"use client";
import Link from "next/link";
import {useCallback,useEffect,useState} from "react";
import {api,siteScope} from "@/lib/api";
import {ErrorState,LoadingState,PageHeader,StatusBadge} from "./ui";
type Eligibility={eligible:boolean;failed_gates:Array<{gate:string;reason:string}>};
type Brief={id:string;status:string;summary:string;exact_query:string;candidate_url:string};
export function ContentBriefs({investigationId}:{investigationId:string}) {
  const [eligibility,setEligibility]=useState<Eligibility>();const [briefs,setBriefs]=useState<Brief[]>([]);const [error,setError]=useState<string>();const [busy,setBusy]=useState(false);
  const load=useCallback(async()=>{try{const scope=siteScope();const [gate,list]=await Promise.all([api<Eligibility>(`/api/v1/seo-investigations/${investigationId}/brief-eligibility?${scope}`),api<{items:Brief[]}>(`/api/v1/seo-investigations/${investigationId}/briefs?${scope}`)]);setEligibility(gate);setBriefs(list.items)}catch(e){setError((e as Error).message)}},[investigationId]);
  useEffect(()=>{void load()},[load]);
  async function generate(){if(!window.confirm("Generate an immutable draft brief? This will not edit or publish the page."))return;setBusy(true);try{await api(`/api/v1/seo-investigations/${investigationId}/briefs/generate?${siteScope()}`,{method:"POST",body:JSON.stringify({actor:"workbench-operator"})});await load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  if(error)return <ErrorState message={error}/>;if(!eligibility)return <LoadingState/>;
  return <><nav className="breadcrumbs"><Link href={`/seo-investigations/${investigationId}`}>Investigation</Link><span>→</span><strong>Content briefs</strong></nav><PageHeader eyebrow="Governed editorial artifacts" title="Evidence-backed content briefs" description="Draft recommendations remain separate from approval, implementation, publication, and measurement."/><section className="semanticSection"><h2>Eligibility</h2><StatusBadge>{eligibility.eligible?"Eligible":"Not eligible"}</StatusBadge>{eligibility.failed_gates.length?<ul>{eligibility.failed_gates.map(item=><li key={`${item.gate}-${item.reason}`}><strong>{item.gate}</strong>: {item.reason}</li>)}</ul>:<p>All deterministic gates pass. Generation still requires an explicit operator action.</p>}{eligibility.eligible?<button disabled={busy} onClick={()=>void generate()}>{busy?"Generating…":"Generate evidence-backed brief"}</button>:null}</section><section className="semanticSection"><h2>Version history</h2>{briefs.length?<div className="recordGrid">{briefs.map(brief=><article className="recordCard" key={brief.id}><h3><Link href={`/seo-investigations/${investigationId}/briefs/${brief.id}`}>{brief.exact_query}</Link></h3><StatusBadge>{brief.status}</StatusBadge><p>{brief.summary}</p><p>{brief.candidate_url}</p></article>)}</div>:<p>No brief has been generated. No content change has been proposed or implemented.</p>}</section></>;
}
