import {ContentBriefs} from "@/components/content-briefs";

export default async function Page({params}:{params:Promise<{id:string}>}) {
  const {id}=await params;
  return <ContentBriefs investigationId={id}/>;
}
