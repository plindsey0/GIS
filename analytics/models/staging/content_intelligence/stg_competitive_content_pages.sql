select
  o.*, d.title, d.meta_description, d.robots_directives, d.normalized_word_count,
  d.paragraph_count, d.h1_count, d.h2_count, d.h3_count, d.ordered_list_count,
  d.unordered_list_count, d.table_count, d.image_count, d.video_count,
  d.form_count, d.iframe_count, d.internal_link_count, d.external_link_count,
  d.publication_dates, d.modified_dates, d.metric_semantics
from {{ ref('stg_competitive_content_observations') }} o
join {{ source('gis_raw', 'competitive_content_document') }} d
  on d.observation_id = o.observation_id
where o.retrieval_status = 'HTTP_SUCCESS'
