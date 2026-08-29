select tenant_id, site_id, observed_date as date, query,
  sum(impressions) as impressions, sum(clicks) as clicks,
  {{ safe_divide('sum(clicks)', 'sum(impressions)') }} as ctr,
  {{ safe_divide('sum(position * impressions)', 'sum(impressions)') }} as weighted_avg_position,
  count(distinct {{ page_key('site_id', normalize_path('page')) }}) as page_count
from {{ ref('stg_gsc_search_observations') }}
where collection_grain in ('query-page', 'query_page') and query is not null
group by 1, 2, 3, 4
