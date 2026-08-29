{% macro normalize_path(expression) -%}
  case
    when nullif(split_part(split_part(regexp_replace({{ expression }}, '^https?://[^/]+', ''), '?', 1), '#', 1), '') is null then '/'
    when split_part(split_part(regexp_replace({{ expression }}, '^https?://[^/]+', ''), '?', 1), '#', 1) = '/' then '/'
    else regexp_replace(split_part(split_part(regexp_replace({{ expression }}, '^https?://[^/]+', ''), '?', 1), '#', 1), '/+$', '')
  end
{%- endmacro %}

{% macro normalize_host(expression) -%}
  nullif(lower(substring({{ expression }} from '^https?://([^/:?#]+)')), '')
{%- endmacro %}

{% macro page_key(site_id, normalized_path) -%}
  md5(({{ site_id }})::text || '|' || {{ normalized_path }})
{%- endmacro %}
