with metrics as (
  select market_observation_id,
    max(metric_value) filter (where metric_key='OBSERVED_DOMAIN_COUNT') as observed_domain_count,
    max(metric_value) filter (where metric_key='MARKET_HHI') as observed_visibility_hhi,
    max(metric_value) filter (where metric_key='EFFECTIVE_COMPETITOR_COUNT') as effective_competitor_count,
    max(metric_value) filter (where metric_key='TOTAL_PROVIDER_SEARCH_VOLUME') as provider_reported_search_volume
  from {{ ref('stg_market_metric_observations') }} group by 1
), participants as (
  select market_observation_id,
    sum(visibility_share) filter (where ownership='OWNED') as owned_visibility_share,
    count(*) filter (where participant_class='DIRECT') as direct_participant_count,
    count(*) filter (where participant_class='ADJACENT') as adjacent_participant_count
  from {{ ref('stg_market_participant_observations') }} group by 1
)
select o.tenant_id, o.site_id, o.market_definition_id, o.market_definition_version,
       o.effective_date as date, o.country_code, o.language_code, o.device,
       o.method_key, o.method_version, o.coverage_status, o.configured_query_count,
       o.observed_query_count, o.query_coverage_rate, o.source_coverage,
       m.observed_domain_count, m.observed_visibility_hhi, m.effective_competitor_count,
       m.provider_reported_search_volume, p.owned_visibility_share,
       coalesce(p.direct_participant_count,0) as direct_participant_count,
       coalesce(p.adjacent_participant_count,0) as adjacent_participant_count,
       o.estimated_cost, o.provider_reported_cost,
       'OBSERVABLE_DIGITAL_MARKET_NOT_ECONOMIC_MARKET' as semantics
from {{ ref('stg_market_observations') }} o
left join metrics m using (market_observation_id)
left join participants p using (market_observation_id)
