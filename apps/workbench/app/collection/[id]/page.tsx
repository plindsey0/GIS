import {SemanticDetail} from "@/components/semantic-detail";
export default async function Page({params}: {params: Promise<{id: string}>}) { const {id} = await params; return <SemanticDetail endpoint={`/api/v1/collection/${id}`} eyebrow="Collection target" fallback="Collection target"/>; }
