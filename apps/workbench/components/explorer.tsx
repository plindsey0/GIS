"use client";

import Link from "next/link";
import {usePathname, useRouter, useSearchParams} from "next/navigation";
import {Suspense, useEffect, useMemo, useState} from "react";
import {api, siteScope} from "@/lib/api";
import {formatDate, formatNumber, humanize} from "@/lib/format";
import type {Page} from "@/lib/types";
import {EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge} from "./ui";

type Item = Record<string, unknown>;
type Filter = {name: string; label: string; options?: {value: string; label: string}[]; optionsKey?: string};
type Column = {key: string; label: string; format?: "date" | "count" | "decimal" | "currency" | "list"};

type ExplorerProps = {title: string; description: string; endpoint: string; empty: string; columns: Column[]; filters?: Filter[]; optionsEndpoint?: string};

function ExplorerInner({title, description, endpoint, empty, columns, filters = [], optionsEndpoint}: ExplorerProps) {
  const router = useRouter(); const pathname = usePathname(); const searchParams = useSearchParams();
  const query = useMemo(() => new URLSearchParams(searchParams.toString()), [searchParams]);
  const [data, setData] = useState<Page<Item>>(); const [error, setError] = useState<string>();
  const [dynamicOptions, setDynamicOptions] = useState<Record<string, {value:string;label:string}[]>>({});
  const page = Number(query.get("page") ?? 1); const limit = Number(query.get("limit") ?? 25);
  useEffect(() => { const scoped = siteScope(); query.forEach((value, key) => scoped.set(key, value)); api<Page<Item>>(`${endpoint}?${scoped}`).then(setData).catch((value: Error) => setError(value.message)); }, [endpoint, query]);
  useEffect(() => { if (optionsEndpoint) api<Record<string,{value:string;label:string}[]>>(`${optionsEndpoint}?${siteScope()}`).then(setDynamicOptions).catch((value:Error)=>setError(value.message)); }, [optionsEndpoint]);
  function update(name: string, value: string) { const next = new URLSearchParams(query); if (value) next.set(name, value); else next.delete(name); if (name !== "page") next.set("page", "1"); router.push(`${pathname}?${next}`); }
  const from = data?.total ? (page - 1) * limit + 1 : 0; const to = data ? Math.min(page * limit, data.total) : 0;
  return <><PageHeader eyebrow="Intelligence explorer" title={title} description={description}/><div className="filterBar"><label>Search subject<input aria-label="Search subject" value={query.get("search") ?? ""} onChange={(event) => update("search", event.target.value)} placeholder="Domain, query, or URL…"/></label>{filters.map((filter) => <label key={filter.name}>{filter.label}<select value={query.get(filter.name) ?? ""} onChange={(event) => update(filter.name, event.target.value)}><option value="">All</option>{(filter.optionsKey?dynamicOptions[filter.optionsKey]??[]:filter.options??[]).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>)}<label>Page size<select value={limit} onChange={(event) => update("limit", event.target.value)}><option>25</option><option>50</option><option>100</option></select></label></div>{error ? <ErrorState message={error}/> : !data ? <LoadingState/> : data.items.length === 0 ? <EmptyState title={empty} detail="The current filters may exclude available governed records. Missing does not mean zero."/> : <><div className="tableWrap"><table><thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{data.items.map((item) => <tr key={String(item.id)}>{columns.map((column) => { const value = item[column.key]; const display = column.format === "date" ? formatDate(value) : column.format === "count" ? formatNumber(value) : column.format === "decimal" ? formatNumber(value, "decimal") : column.format === "currency" ? formatNumber(value, "currency") : column.format === "list" && Array.isArray(value) ? value.map(item=>humanize(String(item))).join(", ") || "None recorded" : String(value ?? "Unknown"); return <td data-label={column.label} key={column.key}>{column.key === "label" && item.href ? <Link href={String(item.href)}>{display}</Link> : column.key === "status" ? <StatusBadge>{humanize(display)}</StatusBadge> : column.key === "evidence_type" ? humanize(display) : display}</td>; })}</tr>)}</tbody></table></div><nav className="pagination" aria-label="Pagination"><p>Showing {from}–{to} of {data.total}</p><button disabled={page <= 1} onClick={() => update("page", String(page - 1))}>Previous</button><span>Page {page} of {Math.max(1, Math.ceil(data.total / limit))}</span><button disabled={to >= data.total} onClick={() => update("page", String(page + 1))}>Next</button></nav></>}</>;
}

export function Explorer(props: ExplorerProps) { return <Suspense fallback={<LoadingState/>}><ExplorerInner {...props}/></Suspense>; }
