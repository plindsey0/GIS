select id as opportunity_evaluation_id, opportunity_id, evaluated_at,
       computed_status::text as computed_status, qualifies, reasons_json, blockers_json,
       metrics_json, created_at
from {{ source('gis_core', 'opportunity_evaluation') }}
