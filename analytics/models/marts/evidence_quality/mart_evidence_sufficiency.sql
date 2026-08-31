select tenant_id, site_id, condition_key, sufficiency, count(*) as package_count
from {{ ref('mart_evidence_quality_current') }} group by 1, 2, 3, 4

