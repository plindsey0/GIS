import {SEOMeasurementDetail} from "@/components/seo-measurement-detail";
export default async function Page({params}:{params:Promise<{id:string;plan_id:string}>}) {const {id,plan_id}=await params;return <SEOMeasurementDetail investigationId={id} planId={plan_id}/>}
