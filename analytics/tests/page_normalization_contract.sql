with examples(source_value, expected_path) as (
  values
    ('https://VAHomeMath.com/va-loan-calculator/?utm_source=test#top', '/va-loan-calculator'),
    ('/va-loan-calculator/', '/va-loan-calculator'),
    ('', '/')
)
select * from examples where {{ normalize_path('source_value') }} <> expected_path
