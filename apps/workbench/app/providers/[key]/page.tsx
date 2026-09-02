import {ProviderDetail} from "../../../components/providers";
export default async function Page({params}:{params:Promise<{key:string}>}){const {key}=await params;return <ProviderDetail providerKey={key}/>}
