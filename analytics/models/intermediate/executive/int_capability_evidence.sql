with evidence as (
  select tenant_id, site_id, 'FIRST_PARTY_TELEMETRY' as capability_key,
         count(*) as evidence_count, max(received_at) as latest_evidence_at
  from {{ ref('stg_events') }} group by 1,2
  union all
  select tenant_id, site_id, 'SEARCH_CONSOLE', count(*), max(ingested_at)
  from {{ ref('stg_gsc_search_observations') }} group by 1,2
  union all
  select tenant_id, site_id, 'WEB_ANALYTICS', count(*), max(ingested_at)
  from {{ ref('stg_ga4_acquisition') }} group by 1,2
  union all
  select tenant_id, site_id, 'SERP_INTELLIGENCE', count(*), max(observed_at)
  from {{ ref('stg_serp_observations') }} group by 1,2
  union all
  select tenant_id, site_id, 'EXTERNAL_SEARCH', count(*), max(observed_at)
  from {{ ref('stg_external_search_observations') }} group by 1,2
  union all
  select tenant_id, site_id, 'COMPETITIVE_CONTENT', count(*), max(observed_at)
  from {{ ref('stg_competitive_content_observations') }} group by 1,2
  union all
  select tenant_id, site_id, 'COMPETITIVE_TECHNOLOGY', count(*), max(observed_at)
  from {{ ref('stg_technology_observations') }} group by 1,2
  union all
  select tenant_id, site_id, 'COMPETITIVE_EVENTS', count(*), max(created_at)
  from {{ ref('stg_competitive_events') }} group by 1,2
  union all
  select tenant_id, site_id, 'AUTHORITY', count(*), max(created_at)
  from {{ ref('stg_authority_observations') }} group by 1,2
  union all
  select tenant_id, site_id, 'MARKET_INTELLIGENCE', count(*), max(created_at)
  from {{ ref('stg_market_observations') }} group by 1,2
  union all
  select tenant_id, site_id, 'COLLECTION_PLANNING', count(*), max(created_at)
  from {{ ref('stg_collection_planning_runs') }} group by 1,2
  union all
  select tenant_id, site_id, 'EMERGING_DEMAND', count(*), max(created_at)
  from {{ ref('stg_demand_analysis_runs') }} group by 1,2
  union all
  select tenant_id, site_id, 'EVIDENCE_QUALITY', count(*), max(created_at)
  from {{ ref('stg_evidence_quality_runs') }} group by 1,2
)
select * from evidence
