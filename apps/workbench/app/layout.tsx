import Link from "next/link";
import type {Metadata} from "next";
import "./globals.css";
import "./exploration.css";
import "./polish.css";
import "./docs.css";

export const metadata: Metadata = {title: "GIS Intelligence Workbench", description: "Governed growth decision intelligence"};
const links = [["/", "Overview"], ["/opportunities", "Opportunities"], ["/recommendations", "Recommendations"], ["/interventions", "Interventions"], ["/evidence", "Evidence"], ["/markets", "Market"], ["/collection", "Collection"], ["/experiments", "Experiments"], ["/outcomes", "Outcomes"], ["/system", "System"], ["/docs", "Learn GIS"]];
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body><div className="shell"><aside><Link className="brand" href="/"><span>GIS</span><strong>Intelligence Workbench</strong></Link><nav aria-label="Primary">{links.map(([href, label]) => <Link key={href} href={href}>{label}</Link>)}</nav><a className="metabase" href={process.env.NEXT_PUBLIC_METABASE_URL ?? "http://localhost:3030"}>Open analytical dashboards ↗</a></aside><main>{children}</main></div></body></html>; }
