select id as analysis_run_id, tenant_id, site_id, market_definition_id,
       market_definition_version, policy_version, analyzed_at, fingerprint,
       observation_count, signal_count, metadata, created_at
from {{ source('gis_core', 'demand_analysis_run') }}

