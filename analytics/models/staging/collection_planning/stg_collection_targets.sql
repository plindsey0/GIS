select id as target_id, tenant_id, site_id, market_definition_id, market_definition_version,
       target_type, normalized_identity, identity_hash, display_value, country_code,
       language_code, device, status, discovered_at, activated_at, paused_at,
       dormant_at, retired_at, human_managed, current_policy_version,
       provenance_metadata, metadata, created_at, updated_at
from {{ source('gis_core', 'collection_target') }}
