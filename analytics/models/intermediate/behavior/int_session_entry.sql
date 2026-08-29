select
  s.*,
  {{ page_key('s.site_id', normalize_path('s.landing_path')) }} as page_key,
  {{ normalize_path('s.landing_path') }} as normalized_path,
  {{ classify_channel(
    source='s.initial_utm_source',
    medium='s.initial_utm_medium',
    has_paid_click="(s.initial_gclid is not null or s.initial_msclkid is not null)",
    referrer='s.referrer_domain'
  ) }} as gis_channel
from {{ ref('stg_sessions') }} s
