select k.tenant_id, k.site_id, k.date, k.query, p.normalized_path,
  kp.impressions, kp.clicks, kp.ctr, kp.position as weighted_avg_position,
  k.page_count
from gis_analytics.mart_keyword_page_daily kp
join gis_analytics.mart_keyword_daily k using (tenant_id, site_id, date, query)
left join gis_analytics.mart_page_daily p
  on p.tenant_id = kp.tenant_id and p.site_id = kp.site_id
  and p.date = kp.date and p.page_key = kp.page_key
where 1=1 [[and k.tenant_id::text = {{tenant_id}}]] [[and k.site_id::text = {{site_id}}]]
  [[and k.date >= {{start_date}}]] [[and k.date <= {{end_date}}]]
  [[and k.query ilike '%' || {{query}} || '%']]
  [[and p.normalized_path ilike '%' || {{page}} || '%']]
order by kp.impressions desc, kp.clicks desc
