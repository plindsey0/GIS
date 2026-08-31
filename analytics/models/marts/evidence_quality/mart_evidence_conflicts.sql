select * from {{ ref('mart_evidence_quality_current') }} where conflict_count > 0

