select id as recommendation_review_id, recommendation_id, decision::text as decision,
 reviewer, reason_category, comment, accepted_candidate_ids_json, reviewed_at
from {{ source('gis_core', 'recommendation_review') }}
