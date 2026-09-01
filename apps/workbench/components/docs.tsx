"use client";

import Link from "next/link";
import {useEffect, useMemo, useState} from "react";
import {usePathname} from "next/navigation";
import {api, siteScope} from "@/lib/api";
import {docGroups, docs, type DocPage, type DocSection} from "@/content/docs";
import {humanize} from "@/lib/format";

export function DocsNav() {
  const pathname = usePathname();
  const [search, setSearch] = useState("");
  const matches = useMemo(() => docs.filter((page) => `${page.title} ${page.summary} ${page.sections.map((section) => `${section.title} ${section.paragraphs?.join(" ") ?? ""}`).join(" ")}`.toLowerCase().includes(search.toLowerCase())), [search]);
  return <aside className="docsNav"><Link className="docsHome" href="/docs">Learn GIS</Link><label>Search documentation<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search concepts…"/></label>{docGroups.map((group) => {const pages = matches.filter((page) => page.group === group); return pages.length ? <section key={group}><h2>{group}</h2>{pages.map((page) => <Link className={pathname === `/docs/${page.slug}` ? "active" : ""} key={page.slug} href={`/docs/${page.slug}`}>{page.title}</Link>)}</section> : null;})}{matches.length === 0 ? <p>No documentation matched.</p> : null}</aside>;
}

function Section({section}: {section: DocSection}) {
  return <section className="docSection" id={section.id}><h2><a href={`#${section.id}`}>{section.title}</a></h2>{section.callout ? <div className="docCallout"><strong>{section.callout.title}</strong><p>{section.callout.text}</p></div> : null}{section.paragraphs?.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}{section.bullets ? <ul>{section.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul> : null}{section.steps ? <ol>{section.steps.map((step) => <li key={step}>{step}</li>)}</ol> : null}{section.diagram ? <div className="conceptDiagram" role="img" aria-label={`${section.title} conceptual flow`}>{section.diagram.map((line) => <div key={line}>{line}</div>)}</div> : null}{section.terms ? <dl className="docsTerms">{section.terms.map((item) => <div key={item.term}><dt>{item.term}</dt><dd>{item.definition}</dd></div>)}</dl> : null}{section.links ? <div className="docLinks">{section.links.map((link) => <Link key={link.href} href={link.href}>{link.label} →</Link>)}</div> : null}</section>;
}

export function DocArticle({page, live = false}: {page: DocPage; live?: boolean}) {
  return <article className="docArticle"><nav className="breadcrumbs" aria-label="Breadcrumb"><Link href="/docs">Documentation</Link><span>→</span><strong>{page.title}</strong></nav><p className="eyebrow">{page.group}</p><h1>{page.title}</h1><p className="docLead">{page.summary}</p><nav className="docToc" aria-label="On this page"><strong>On this page</strong>{page.sections.map((section) => <a key={section.id} href={`#${section.id}`}>{section.title}</a>)}</nav>{live ? <LiveState/> : null}{page.sections.map((section) => <Section key={section.id} section={section}/>)}</article>;
}

type Evidence = {total: number}; type Opportunities = {total: number}; type Pipelines = {total:number;health_counts:Record<string,number>}; type Markets = {items:{label?:string;name?:string}[]};
export function LiveState() {
  const [state, setState] = useState<{evidence:number;opportunities:number;pipelines:number;attention:number;market:string} | null>(null);
  useEffect(() => {const scope=siteScope(); Promise.all([api<Evidence>(`/api/v1/evidence/packages?${scope}`),api<Opportunities>(`/api/v1/opportunities?${scope}`),api<Pipelines>(`/api/v1/system/pipelines?${scope}`),api<Markets>(`/api/v1/markets?${scope}`)]).then(([evidence,opportunities,pipelines,markets])=>setState({evidence:evidence.total,opportunities:opportunities.total,pipelines:pipelines.total,attention:(pipelines.health_counts.FAILING??0)+(pipelines.health_counts.STALE??0)+(pipelines.health_counts.INSUFFICIENT_HISTORY??0),market:markets.items[0]?.label??markets.items[0]?.name??"No active market"})).catch(()=>setState(null));},[]);
  if (!state) return <aside className="liveState"><strong>Current live state</strong><p>Live counts are unavailable. Conceptual documentation remains valid; use System for operational details.</p></aside>;
  return <aside className="liveState"><strong>Current live state</strong><p>These values come from the API and are not maintained documentation.</p><div><span><b>{state.market}</b>Market</span><span><b>{state.evidence}</b>Evidence packages</span><span><b>{state.opportunities}</b>Opportunities</span><span><b>{state.pipelines}</b>Pipelines</span><span><b>{state.attention}</b>Need history or attention</span></div></aside>;
}

export function DocsLanding() {
  return <article className="docArticle docsLanding"><p className="eyebrow">Product knowledge base</p><h1>Learn GIS</h1><p className="docLead">Understand how GIS observes a market, builds evidence, supports decisions, preserves governance, and learns from outcomes.</p><LiveState/><div className="docCards">{docs.map((page) => <Link key={page.slug} href={`/docs/${page.slug}`}><small>{humanize(page.group)}</small><strong>{page.title}</strong><span>{page.summary}</span></Link>)}</div></article>;
}
