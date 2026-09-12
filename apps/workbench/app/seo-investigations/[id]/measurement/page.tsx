import {SEOMeasurementPlans} from "@/components/seo-measurement";
export default async function Page({params}:{params:Promise<{id:string}>}) {const {id}=await params;return <SEOMeasurementPlans investigationId={id}/>}
