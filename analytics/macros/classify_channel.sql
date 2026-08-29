{% macro classify_channel(provider_channel='null', source='null', medium='null', has_paid_click='false', referrer='null') -%}
case
  when {{ has_paid_click }} then 'paid_search'
  when lower(coalesce({{ provider_channel }}, '')) like '%paid search%' or lower(coalesce({{ medium }}, '')) in ('cpc', 'ppc', 'paidsearch') then 'paid_search'
  when lower(coalesce({{ provider_channel }}, '')) like '%organic search%' or lower(coalesce({{ medium }}, '')) = 'organic' then 'organic_search'
  when lower(coalesce({{ provider_channel }}, '')) like '%organic social%' or lower(coalesce({{ medium }}, '')) like '%social%' then 'social'
  when lower(coalesce({{ provider_channel }}, '')) like '%email%' or lower(coalesce({{ medium }}, '')) = 'email' then 'email'
  when lower(coalesce({{ provider_channel }}, '')) like '%direct%' or (nullif({{ source }}, '') is null and nullif({{ referrer }}, '') is null) then 'direct'
  when lower(coalesce({{ provider_channel }}, '')) like '%referral%' or nullif({{ referrer }}, '') is not null then 'referral'
  when nullif({{ provider_channel }}, '') is null and nullif({{ source }}, '') is null and nullif({{ medium }}, '') is null then 'unknown'
  else 'other'
end
{%- endmacro %}
