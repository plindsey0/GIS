import Link from "next/link";
import type {ReactNode} from "react";

export function PageHeader({eyebrow, title, description}: {eyebrow: string; title: string; description: string}) {
  return <header className="pageHeader"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></header>;
}
export function StatusBadge({children, domain = "neutral"}: {children: ReactNode; domain?: string}) {
  return <span className={`badge badge-${domain}`}>{children}</span>;
}
export function MetricCard({label, value, detail}: {label: string; value: number | string | null; detail: string}) {
  return <article className="metric"><p>{label}</p><strong>{value ?? "—"}</strong><small>{detail}</small></article>;
}
export function EmptyState({title, detail}: {title: string; detail: string}) {
  return <div className="state" role="status"><h2>{title}</h2><p>{detail}</p></div>;
}
export function ErrorState({message}: {message: string}) {
  return <div className="state error" role="alert"><h2>GIS could not load this view</h2><p>{message}</p></div>;
}
export function LoadingState() { return <div className="state" role="status" aria-live="polite">Loading current GIS state…</div>; }
export function EntityLink({href, children}: {href: string; children: ReactNode}) { return <Link className="entityLink" href={href}>{children}</Link>; }
