select tenant_id, site_id, market_definition_id, market_definition_version,
       effective_date as date, count(*) as unique_domain_count,
       sum(serp_appearance_count) as organic_result_appearances,
       avg(query_count) as average_queries_per_domain,
       count(*) filter (where query_count>1) as recurring_domain_count,
       sum(visibility_share*visibility_share) as domain_concentration,
       'OBSERVED_ORGANIC_RESULTS_ONLY' as coverage_semantics
from {{ ref('stg_market_participant_observations') }} group by 1,2,3,4,5
