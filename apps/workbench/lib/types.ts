export type ApiError = {error: {code: string; message: string; request_id: string; details: unknown; retryable: boolean}};
export type Page<T> = {items: T[]; page: number; limit: number; total: number};
export type Overview = {
  opportunities_to_review: number;
  recommendations_to_review: number;
  interventions_to_approve: number;
  active_interventions: number;
  experiments_running: number;
  recent_outcomes: number;
  search: {stored_observations: number; latest_observation: string | null; rights_state: string; blocker: string | null; clicks: string | null; impressions: string | null; ctr: string | null; average_position: string | null; observed_query_count: number | null};
  traffic: {stored_event_observations: number; stored_landing_page_observations: number; latest_observation: string | null; rights_state: string; blocker: string | null; events: string | null; users: string | null; sessions: string | null};
  visibility: {stored_serp_observations: number; stored_serp_results: number; latest_observation: string | null; rights_state: string; blocker: string | null; tracked_query_count: number | null};
  market: {id: string | null; name: string | null; version: number | null; definition_member_count: number; observation_count: number; participant_count: number};
  demand: {stored_external_keywords: number; stored_external_observations: number; demand_observations: number; demand_signals: number; latest_provider_observation: string | null; rights_state: string; blocker: string | null; provider_specific_volume: string | null};
  evidence: {packages: number; gaps: number; status: string; explanation: string};
  competitive: {content_observations: number; technology_observations: number; technology_detections: number; events: number; latest_event: string | null; rights_state: string};
  collection_health: {targets: number; query_targets: number; domain_targets: number; url_targets: number; latest_update: string | null};
  unknown_values_are_zero: false;
};
export type Opportunity = {
  id: string; title: string; family: string; opportunity_type: string; status: string;
  priority: string; evidence_sufficiency: string; entity_type: string; entity_key: string;
  detected_at: string; recommendation_status: string | null; intervention_status: string | null;
};
export type Resource = {id: string; resource_type: string; data: Record<string, unknown>};
