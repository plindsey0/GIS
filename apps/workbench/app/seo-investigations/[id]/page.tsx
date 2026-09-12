import {SEOInvestigationDetail} from "@/components/seo-investigation-detail";

export default async function Page({params}: {params: Promise<{id: string}>}) {
  const {id} = await params;
  return <SEOInvestigationDetail id={id}/>;
}
