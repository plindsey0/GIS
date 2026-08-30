select *, observed_at::date as date
from {{ ref('stg_competitive_content_pages') }}
