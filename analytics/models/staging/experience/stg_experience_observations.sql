select id as observation_id, tenant_id, site_id, ingestion_run_id,
  data_source_connection_id as connection_id, rights_policy_id, rights_policy_version,
  observed_at, period_start, period_end, target, normalized_target, measurement_type,
  scope, form_factor, availability, metric, metric_value, unit, percentile,
  classification, good_proportion, needs_improvement_proportion, poor_proportion
from {{ source('gis_raw', 'experience_observation') }}
