import Link from "next/link";
import type {Metadata} from "next";
import "./globals.css";
import "./exploration.css";
import "./polish.css";
import "./docs.css";
import {PrimaryNavigation} from "../components/navigation";

export const metadata: Metadata = {title: "GIS Intelligence Workbench", description: "Governed growth decision intelligence"};
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body><div className="shell"><aside><Link className="brand" href="/"><span>GIS</span><strong>Intelligence Workbench</strong></Link><PrimaryNavigation/><a className="metabase" href={process.env.NEXT_PUBLIC_METABASE_URL ?? "http://localhost:3030"}>Open analytical dashboards ↗</a></aside><main>{children}</main></div></body></html>; }
