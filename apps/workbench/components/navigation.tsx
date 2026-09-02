"use client";
import Link from "next/link";
import {usePathname} from "next/navigation";
const links=[["/","Overview"],["/goals","Goals"],["/opportunities","Opportunities"],["/recommendations","Recommendations"],["/interventions","Interventions"],["/evidence","Evidence"],["/markets","Market"],["/collection","Collection"],["/experiments","Experiments"],["/outcomes","Outcomes"],["/system","System"],["/docs","Learn GIS"]];
export function PrimaryNavigation(){const pathname=usePathname();return <nav aria-label="Primary">{links.map(([href,label])=>{const active=href==="/"?pathname===href:pathname===href||pathname.startsWith(`${href}/`);return <Link key={href} href={href} className={active?"active":undefined} aria-current={active?"page":undefined}>{label}</Link>})}</nav>}
