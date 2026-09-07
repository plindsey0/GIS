import {ProposalDetail} from "@/components/intelligence-workbench";
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <ProposalDetail id={id}/>}
