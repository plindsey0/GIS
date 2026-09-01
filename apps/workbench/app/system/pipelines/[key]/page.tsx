import {SemanticDetail} from "@/components/semantic-detail";
export default async function Page({params}:{params:Promise<{key:string}>}){const{key}=await params;return <SemanticDetail endpoint={`/api/v1/system/pipelines/${key}`} eyebrow="Pipeline" fallback={key}/>}
