import {ContentBriefDetail} from "@/components/content-brief-detail";

export default async function Page({params}:{params:Promise<{id:string;brief_id:string}>}) {
  const {id,brief_id}=await params;
  return <ContentBriefDetail investigationId={id} briefId={brief_id}/>;
}
