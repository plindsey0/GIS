select tenant_id, site_id, date,
       gsc_clicks as organic_clicks, gsc_impressions as organic_impressions,
       gsc_ctr as organic_ctr, gsc_avg_position as search_position,
       ga4_sessions as sessions, ga4_active_users as active_users,
       first_party_sessions, calculator_starts, calculator_completions,
       cta_clicks, conversions, session_conversion_rate as conversion_rate,
       not ('MISSING_GSC' = any(data_quality_flags)) as search_data_available,
       not ('MISSING_GA4' = any(data_quality_flags)) as analytics_data_available,
       not ('MISSING_FIRST_PARTY' = any(data_quality_flags)) as telemetry_data_available,
       data_quality_flags
from {{ ref('mart_site_daily') }}
