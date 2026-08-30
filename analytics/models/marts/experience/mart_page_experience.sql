select tenant_id, site_id, period_end, normalized_target, measurement_type, scope,
  form_factor, availability,
  max(metric_value) filter (where metric = 'LCP') as lcp,
  max(metric_value) filter (where metric = 'INP') as inp,
  max(metric_value) filter (where metric = 'CLS') as cls,
  max(classification) filter (where metric = 'LCP') as lcp_status,
  max(classification) filter (where metric = 'INP') as inp_status,
  max(classification) filter (where metric = 'CLS') as cls_status
from {{ ref('stg_experience_observations') }}
group by 1,2,3,4,5,6,7,8
