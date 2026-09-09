import {SemanticDetail} from "@/components/semantic-detail";

export default async function QueryPageIntentPage({params}: {params: Promise<{id: string}>}) {
  const {id} = await params;
  return <SemanticDetail
    endpoint={`/query-page-intent/${id}`}
    eyebrow="Query ↔ Page ↔ Intent"
    fallback="Governed query-page relationship"
  />;
}
