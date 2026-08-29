with violations as (
  select 'site' as model, tenant_id, site_id, date, null::text as extra
  from {{ ref('mart_site_daily') }} group by 1, 2, 3, 4 having count(*) > 1
  union all
  select 'page', tenant_id, site_id, date, page_key
  from {{ ref('mart_page_daily') }} group by 1, 2, 3, 4, 5 having count(*) > 1
  union all
  select 'keyword_page', tenant_id, site_id, date, query || '|' || page_key
  from {{ ref('mart_keyword_page_daily') }} group by 1, 2, 3, 4, 5 having count(*) > 1
  union all
  select 'search_funnel', tenant_id, site_id, date, page_key
  from {{ ref('mart_search_funnel') }} group by 1, 2, 3, 4, 5 having count(*) > 1
)
select * from violations
