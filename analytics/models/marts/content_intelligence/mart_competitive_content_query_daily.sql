select tenant_id, site_id, tracked_query_id, observed_at::date as date,
       count(*) as observed_pages,
       percentile_cont(0.5) within group (order by normalized_word_count) as median_word_count,
       avg(h2_count) as average_h2_count,
       sum(case when ownership_class='COMPETITOR' then 1 else 0 end) as competitor_pages
from {{ ref('stg_competitive_content_pages') }}
where tracked_query_id is not null
group by 1,2,3,4
