select id as quality_dimension_id, evidence_package_id, dimension, state,
       method_key, method_version, observed_value, expected_value, reasons_json, created_at
from {{ source('gis_core', 'evidence_quality_dimension') }}

