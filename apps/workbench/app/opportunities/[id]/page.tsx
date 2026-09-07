import {OpportunityDecisionDetail} from "@/components/intelligence-workbench";
export default async function Page({params}: {params: Promise<{id: string}>}) { const {id} = await params; return <OpportunityDecisionDetail id={id}/>; }
