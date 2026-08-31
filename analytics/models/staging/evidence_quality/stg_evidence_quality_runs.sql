select id as quality_run_id, tenant_id, site_id, method_version, assessed_at,
       fingerprint, input_count, package_count, metadata, created_at
from {{ source('gis_core', 'evidence_quality_run') }}

