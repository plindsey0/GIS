{% macro safe_divide(numerator, denominator) -%}
  ({{ numerator }})::numeric / nullif(({{ denominator }})::numeric, 0)
{%- endmacro %}
