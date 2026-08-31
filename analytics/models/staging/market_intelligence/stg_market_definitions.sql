select id as market_definition_id, tenant_id, organization_id, site_id, name, slug,
       description, status, market_type, country_code, language_code, device,
       version, effective_at, superseded_at,
       supersedes_id, created_by, semantic_notes, created_at, updated_at
from {{ source('gis_core', 'market_definition') }}
