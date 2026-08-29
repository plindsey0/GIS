with gsc as (
  select tenant_id, site_id, date, sum(clicks) as gsc_clicks
  from {{ ref('int_search_page_daily') }} group by 1, 2, 3
), ga4_presence as (
  select tenant_id, site_id, observed_date as date
  from {{ ref('stg_ga4_acquisition') }}
  group by 1, 2, 3
), ga4_organic as (
  select tenant_id, site_id, observed_date as date, sum(sessions) as ga4_organic_sessions
  from {{ ref('stg_ga4_acquisition') }}
  where {{ classify_channel('provider_channel', 'source', 'medium') }} = 'organic_search'
  group by 1, 2, 3
), fp as (
  select tenant_id, site_id, analytical_date as date, count(*) as first_party_organic_sessions
  from {{ ref('int_session_entry') }} where gis_channel = 'organic_search' group by 1, 2, 3
), keys as (
  select tenant_id, site_id, date from gsc union select tenant_id, site_id, date from ga4_presence union
  select tenant_id, site_id, date from fp
)
select k.*, coalesce(g.gsc_clicks, 0) as gsc_clicks,
  coalesce(a.ga4_organic_sessions, 0) as ga4_organic_sessions,
  coalesce(f.first_party_organic_sessions, 0) as first_party_organic_sessions,
  g.gsc_clicks - a.ga4_organic_sessions as gsc_to_ga4_delta,
  {{ safe_divide('a.ga4_organic_sessions', 'g.gsc_clicks') }} as gsc_to_ga4_ratio,
  a.ga4_organic_sessions - f.first_party_organic_sessions as ga4_to_first_party_delta,
  {{ safe_divide('f.first_party_organic_sessions', 'a.ga4_organic_sessions') }} as ga4_to_first_party_ratio,
  g.tenant_id is not null as gsc_data_present, p.tenant_id is not null as ga4_data_present,
  f.tenant_id is not null as first_party_data_present,
  case
    when g.tenant_id is null and p.tenant_id is null and f.tenant_id is null then 'NO_TRAFFIC'
    when g.tenant_id is null or p.tenant_id is null or f.tenant_id is null then 'PARTIAL_SOURCE_COVERAGE'
    when abs(1 - {{ safe_divide('a.ga4_organic_sessions', 'g.gsc_clicks') }}) > 0.5 then 'HIGH_GSC_GA4_VARIANCE'
    when abs(1 - {{ safe_divide('f.first_party_organic_sessions', 'a.ga4_organic_sessions') }}) > 0.5 then 'HIGH_GA4_FIRST_PARTY_VARIANCE'
    else 'OBSERVED'
  end as quality_status
from keys k left join gsc g using (tenant_id, site_id, date)
left join ga4_presence p using (tenant_id, site_id, date)
left join ga4_organic a using (tenant_id, site_id, date)
left join fp f using (tenant_id, site_id, date)
