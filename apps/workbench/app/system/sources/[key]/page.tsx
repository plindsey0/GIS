import {SemanticDetail} from "@/components/semantic-detail";
import {SourceGovernance} from "@/components/source-governance";
export default async function Page({params}:{params:Promise<{key:string}>}){const{key}=await params;return <><SourceGovernance sourceKey={key}/><details><summary>Source metadata and historical evidence</summary><SemanticDetail endpoint={`/api/v1/system/sources/${key}`} eyebrow="Data source" fallback={key}/></details></>}
