import {OpportunityCandidate} from "@/components/opportunity-candidate";
export default async function Page({params,searchParams}:{params:Promise<{id:string}>;searchParams:Promise<{detector?:string}>}){const[{id},{detector}]=await Promise.all([params,searchParams]);return <OpportunityCandidate id={id} detector={detector}/>;}
