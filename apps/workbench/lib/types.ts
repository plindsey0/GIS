export type ApiError = {error: {code: string; message: string; request_id: string; details: unknown; retryable: boolean}};
export type Page<T> = {items: T[]; page: number; limit: number; total: number};
export type Overview = {
  opportunities_to_review: number;
  recommendations_to_review: number;
  interventions_to_approve: number;
  active_interventions: number;
  experiments_running: number;
  recent_outcomes: number;
  unknown_values_are_zero: false;
};
export type Opportunity = {
  id: string; title: string; family: string; opportunity_type: string; status: string;
  priority: string; evidence_sufficiency: string; entity_type: string; entity_key: string;
  detected_at: string; recommendation_status: string | null; intervention_status: string | null;
};
export type Resource = {id: string; resource_type: string; data: Record<string, unknown>};
