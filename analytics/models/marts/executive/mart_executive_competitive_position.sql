with search as (
  select tenant_id, site_id, date, ranking_domain as observed_domain, 'SEARCH' as evidence_domain,
         'external_search' as source_system,
         keyword_footprint::numeric as primary_value, 'keyword_footprint' as primary_metric,
         search_volume_weighted_visibility::numeric as secondary_value,
         'search_volume_weighted_visibility' as secondary_metric,
         null::jsonb as provider_metrics, 'OBSERVED_COMPARISON' as semantics
  from {{ ref('mart_search_market_visibility') }}
), content as (
  select tenant_id, site_id, date, domain, 'CONTENT', 'content_observation', observed_pages::numeric,
         'observed_pages', average_word_count::numeric, 'average_word_count', null::jsonb,
         'OBSERVED_COMPARISON'
  from {{ ref('mart_competitive_content_domain_daily') }}
), technology as (
  select tenant_id, site_id, date, domain, 'TECHNOLOGY', 'technology_observation', technology_count::numeric,
         'observed_technology_count', category_count::numeric, 'observed_category_count', null::jsonb,
         'OBSERVED_COMPARISON'
  from {{ ref('mart_technology_competitor_daily') }}
), authority as (
  select tenant_id, site_id, date, target_domain, 'AUTHORITY', provider, backlink_count::numeric,
         'observed_backlink_count', referring_domain_count::numeric, 'observed_referring_domain_count',
         provider_metrics, 'PROVIDER_SPECIFIC_METRICS_NOT_INTERCHANGEABLE'
  from {{ ref('mart_authority_domain_daily') }}
)
select * from search union all select * from content union all select * from technology union all select * from authority
