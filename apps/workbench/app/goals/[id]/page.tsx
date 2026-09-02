import {GoalDetail} from "../../../components/goals";
export default async function Page({params}:{params:Promise<{id:string}>}){const{id}=await params;return <GoalDetail id={id}/>;}
