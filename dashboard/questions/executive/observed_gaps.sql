with gaps as (
  select tenant_id, site_id, date, 'SEARCH' as gap_domain, ranking_domain as observed_item,
         case when externally_discovered_only then 'COMPETITOR_ONLY' else 'SHARED_OBSERVATION' end as gap_class,
         'OBSERVED_DIFFERENCE_NOT_RECOMMENDATION' as semantics
  from gis_analytics.mart_keyword_gap
  union all
  select tenant_id, site_id, null::date, 'TECHNOLOGY', technology_name,
         case when absent_from_owned then 'COMPETITOR_ONLY' else 'SHARED' end, semantics
  from gis_analytics.mart_technology_gap
  union all
  select tenant_id, site_id, date, 'AUTHORITY', referring_domain, observed_gap_class,
         'OBSERVED_DIFFERENCE_NOT_RECOMMENDATION'
  from gis_analytics.mart_authority_gap
)
select date, gap_domain, observed_item, gap_class, semantics from gaps
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and (date is null or date >= {{start_date}})]] [[and (date is null or date <= {{end_date}})]]
order by date desc nulls last, gap_domain, observed_item limit 100
