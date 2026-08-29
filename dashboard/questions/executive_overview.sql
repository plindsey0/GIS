with site as (
  select * from gis_analytics.mart_site_daily
  where 1=1
    [[and tenant_id::text = {{tenant_id}}]] [[and site_id::text = {{site_id}}]]
    [[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
), quality as (
  select tenant_id, site_id, date, gsc_data_present, ga4_data_present, first_party_data_present
  from gis_analytics.mart_data_reconciliation
), ga4_events as (
  select tenant_id, site_id, date, sum(key_events) as key_events
  from gis_analytics.mart_acquisition_daily where provider_channel <> '(first-party only)'
  group by 1,2,3
)
select s.tenant_id, s.site_id, min(s.date) as period_start, max(s.date) as period_end,
  case when bool_or(q.gsc_data_present) then sum(s.gsc_impressions) end as gsc_impressions,
  case when bool_or(q.gsc_data_present) then sum(s.gsc_clicks) end as gsc_clicks,
  case when bool_or(q.gsc_data_present) and sum(s.gsc_impressions) > 0
    then sum(s.gsc_clicks) / sum(s.gsc_impressions) end as gsc_ctr,
  case when bool_or(q.gsc_data_present) and sum(s.gsc_impressions) > 0
    then sum(s.gsc_avg_position * s.gsc_impressions) / sum(s.gsc_impressions) end as gsc_avg_position,
  case when bool_or(q.ga4_data_present) then sum(s.ga4_sessions) end as ga4_sessions,
  case when bool_or(q.ga4_data_present) then sum(s.ga4_active_users) end as ga4_active_users,
  case when bool_or(q.ga4_data_present) then sum(s.ga4_new_users) end as ga4_new_users,
  case when bool_or(q.ga4_data_present) then sum(s.ga4_engaged_sessions) end as ga4_engaged_sessions,
  case when bool_or(q.ga4_data_present) and sum(s.ga4_sessions) > 0
    then sum(s.ga4_engaged_sessions) / sum(s.ga4_sessions) end as ga4_engagement_rate,
  case when bool_or(q.ga4_data_present) then sum(coalesce(e.key_events, 0)) end as ga4_key_events,
  case when bool_or(q.first_party_data_present) then sum(s.first_party_sessions) end as first_party_sessions,
  case when bool_or(q.first_party_data_present) then sum(s.calculator_starts) end as calculator_starts,
  case when bool_or(q.first_party_data_present) then sum(s.calculator_completions) end as calculator_completions,
  case when bool_or(q.first_party_data_present) then sum(s.cta_clicks) end as cta_clicks,
  case when bool_or(q.first_party_data_present) then sum(s.conversions) end as conversions,
  case when bool_or(q.first_party_data_present) then 'AVAILABLE' else 'FIRST_PARTY_NOT_AVAILABLE' end as telemetry_status
from site s left join quality q using (tenant_id, site_id, date)
left join ga4_events e using (tenant_id, site_id, date)
group by 1,2 order by 1,2
