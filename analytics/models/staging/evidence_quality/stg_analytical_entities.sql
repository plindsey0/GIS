select id as analytical_entity_id, tenant_id, site_id, entity_type, canonical_key,
       identity_hash, display_name, country_code, language_code, device, method_key,
       method_version, source_reference_type, source_reference_id, metadata,
       created_at, updated_at
from {{ source('gis_core', 'analytical_entity') }}

