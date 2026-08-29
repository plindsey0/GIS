select 'gsc' as source_name
where (select count(*) from {{ ref('stg_gsc_search_observations') }})
   <> (select count(*) from {{ source('gis_raw', 'gsc_search_observation') }} where effective_end is null)
union all
select 'ga4_landing'
where (select count(*) from {{ ref('stg_ga4_landing_pages') }})
   <> (select count(*) from {{ source('gis_raw', 'ga4_landing_page_observation') }} where effective_end is null)
union all
select 'ga4_acquisition'
where (select count(*) from {{ ref('stg_ga4_acquisition') }})
   <> (select count(*) from {{ source('gis_raw', 'ga4_acquisition_observation') }} where effective_end is null)
union all
select 'ga4_events'
where (select count(*) from {{ ref('stg_ga4_events') }})
   <> (select count(*) from {{ source('gis_raw', 'ga4_event_observation') }} where effective_end is null)
