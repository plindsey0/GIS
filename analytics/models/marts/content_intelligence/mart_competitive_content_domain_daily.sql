select tenant_id, site_id, domain, observed_at::date as date,
       count(*) as observed_pages,
       avg(normalized_word_count) as average_word_count,
       avg(h2_count) as average_h2_count,
       avg(external_link_count) as average_external_link_count
from {{ ref('stg_competitive_content_pages') }}
group by 1,2,3,4
