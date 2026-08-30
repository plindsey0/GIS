select tenant_id, site_id, tracked_query_id, observed_at::date as date, normalized_term,
       extraction_method, metric_semantics, count(distinct observation_id) as page_count,
       sum(occurrence_count) as occurrence_count
from {{ ref('stg_competitive_content_topics') }}
group by 1,2,3,4,5,6,7
