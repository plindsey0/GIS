import {ProviderConfigurationPage} from "../../../components/provider-configuration";
export default async function Page({params}:{params:Promise<{key:string}>}){const {key}=await params;return <ProviderConfigurationPage providerKey={key}/>}
