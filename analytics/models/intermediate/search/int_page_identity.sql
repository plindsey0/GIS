with candidates as (
  select tenant_id, site_id, page as original_value, {{ normalize_host('page') }} as normalized_host,
    {{ normalize_path('page') }} as normalized_path, 'gsc' as source_system
  from {{ ref('stg_gsc_search_observations') }} where page is not null
  union all
  select tenant_id, site_id, landing_page, null,
    {{ normalize_path('landing_page') }}, 'ga4'
  from {{ ref('stg_ga4_landing_pages') }} where landing_page is not null
  union all
  select tenant_id, site_id, landing_path, null,
    {{ normalize_path('landing_path') }}, 'first_party'
  from {{ ref('stg_sessions') }} where landing_path is not null
), grouped as (
  select tenant_id, site_id, normalized_path,
    max(normalized_host) as normalized_host,
    max(original_value) filter (where source_system = 'gsc') as gsc_page_url,
    max(original_value) filter (where source_system = 'ga4') as ga4_landing_page,
    max(original_value) filter (where source_system = 'first_party') as first_party_path,
    count(distinct source_system) as source_count
  from candidates group by 1, 2, 3
)
select *, {{ page_key('site_id', 'normalized_path') }} as page_key from grouped
