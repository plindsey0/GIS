with history as (
  select *, lag(observed_visibility_hhi) over w as prior_hhi,
         lag(owned_visibility_share) over w as prior_owned_visibility_share,
         lag(observed_domain_count) over w as prior_domain_count,
         lag(provider_reported_search_volume) over w as prior_provider_search_volume
  from {{ ref('mart_market_daily') }}
  window w as (partition by tenant_id,site_id,market_definition_id,market_definition_version,method_key,method_version order by date)
)
select *, observed_visibility_hhi-prior_hhi as hhi_change,
       owned_visibility_share-prior_owned_visibility_share as owned_visibility_share_change,
       observed_domain_count-prior_domain_count as domain_count_change,
       provider_reported_search_volume-prior_provider_search_volume as provider_search_volume_change,
       case when prior_hhi is null then 'NO_COMPARABLE_PRIOR_OBSERVATION'
            else 'SAME_DEFINITION_AND_METHOD_VERSION' end as comparability_status
from history
