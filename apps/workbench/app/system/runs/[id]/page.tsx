import {OperationalRun} from "@/components/operational-run";
export default async function Page({params}:{params:Promise<{id:string}>}){const{id}=await params;return <OperationalRun id={id}/>}
