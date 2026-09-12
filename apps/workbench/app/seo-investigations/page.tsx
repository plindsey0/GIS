import {Explorer} from "@/components/explorer";

export default function Page() {
  return <Explorer
    title="SEO investigations"
    description="Move bounded SEO questions through evidence, adjudication, interpretation, and human approval without triggering collection or recommendations from a read."
    endpoint="/api/v1/seo-investigations"
    empty="No SEO investigations match this scope"
    optionsEndpoint="/api/v1/seo-investigations/options"
    columns={[
      {key: "label", label: "Investigation"},
      {key: "query", label: "Exact query"},
      {key: "candidate_page", label: "Candidate page"},
      {key: "status", label: "Stage"},
      {key: "priority", label: "Priority"},
      {key: "evidence_readiness", label: "Evidence readiness"},
      {key: "human_review_required", label: "Human review"},
      {key: "recommendation_eligible", label: "Recommendation eligible"},
    ]}
    filters={[
      {name: "stage", label: "Stage", options: ["EVIDENCE_REQUIRED", "AWAITING_COLLECTION_APPROVAL", "COLLECTION_CANDIDATE", "AWAITING_ADJUDICATION", "CONFLICTING_EVIDENCE", "AWAITING_HUMAN_REVIEW", "READY_FOR_INTERPRETATION", "READY_FOR_RECOMMENDATION", "BLOCKED", "CLOSED_NO_ACTION", "CLOSED"].map(value => ({value, label: value.replaceAll("_", " ")}))},
      {name: "priority", label: "Priority", options: ["CRITICAL", "HIGH", "MEDIUM", "LOW"].map(value => ({value, label: value}))},
      {name: "market_id", label: "Market", optionsKey: "markets"},
      {name: "evidence_readiness", label: "Evidence readiness", options: ["MISSING", "LIMITED", "CONFLICTING", "BLOCKED", "SUPPORTED"].map(value => ({value, label: value}))},
      {name: "human_review_required", label: "Human review", options: [{value: "true", label: "Required"}, {value: "false", label: "Not required"}]},
      {name: "recommendation_eligible", label: "Recommendation eligibility", options: [{value: "true", label: "Eligible"}, {value: "false", label: "Not eligible"}]},
      {name: "sort", label: "Sort", options: [{value:"priority",label:"Priority"},{value:"stage",label:"Stage"},{value:"updated_at",label:"Updated"},{value:"label",label:"Title"}]},
      {name: "order", label: "Order", options: [{value:"asc",label:"Ascending"},{value:"desc",label:"Descending"}]},
    ]}
  />;
}
