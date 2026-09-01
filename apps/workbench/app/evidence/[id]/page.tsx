import {SemanticDetail} from "@/components/semantic-detail";
export default async function Page({params}: {params: Promise<{id: string}>}) { const {id} = await params; return <SemanticDetail endpoint={`/api/v1/evidence/packages/${id}`} eyebrow="Evidence package" fallback="Evidence package"/>; }
