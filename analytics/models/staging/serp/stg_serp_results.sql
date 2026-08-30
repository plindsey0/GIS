select id as result_id, serp_observation_id as observation_id, rank_absolute, rank_group,
  feature_type, provider_type, url, normalized_url, hostname, title, snippet,
  is_paid, is_organic, is_feature, ownership, created_at
from {{ source('gis_raw', 'serp_result') }}
