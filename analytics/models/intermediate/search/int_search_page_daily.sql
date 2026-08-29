with page_grain as (
  select tenant_id, site_id, observed_date as date,
    {{ page_key('site_id', normalize_path('page')) }} as page_key,
    {{ normalize_path('page') }} as normalized_path,
    sum(impressions) as impressions, sum(clicks) as clicks,
    {{ safe_divide('sum(position * impressions)', 'sum(impressions)') }} as avg_position
  from {{ ref('stg_gsc_search_observations') }}
  where collection_grain = 'page'
  group by 1, 2, 3, 4, 5
), query_fallback as (
  select g.tenant_id, g.site_id, g.observed_date as date,
    {{ page_key('g.site_id', normalize_path('g.page')) }} as page_key,
    {{ normalize_path('g.page') }} as normalized_path,
    sum(g.impressions) as impressions, sum(g.clicks) as clicks,
    {{ safe_divide('sum(g.position * g.impressions)', 'sum(g.impressions)') }} as avg_position
  from {{ ref('stg_gsc_search_observations') }} g
  where g.collection_grain in ('query-page', 'query_page')
    and not exists (
      select 1 from page_grain p
      where p.tenant_id = g.tenant_id and p.site_id = g.site_id and p.date = g.observed_date
    )
  group by 1, 2, 3, 4, 5
), combined as (
  select * from page_grain union all select * from query_fallback
)
select *, {{ safe_divide('clicks', 'impressions') }} as ctr from combined
