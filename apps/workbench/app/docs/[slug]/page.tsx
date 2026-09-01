import {notFound} from "next/navigation";
import {DocArticle} from "@/components/docs";
import {docs, docsBySlug} from "@/content/docs";
export function generateStaticParams(){return docs.map((page)=>({slug:page.slug}))}
export default async function Page({params}:{params:Promise<{slug:string}>}){const{slug}=await params;const page=docsBySlug.get(slug);if(!page)notFound();return <DocArticle page={page} live={slug==="overview"||slug==="limitations"}/>}
