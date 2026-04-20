{{ config(materialized='view') }}

select
      person_id,
      person_id           as person_source_value,
      birth_year,
      birth_month,
      birth_day,
      gender_source_value,
      race_source_value,
      ethnicity_source_value,
      location_state,
      loaded_at
  from {{ source('raw', 'raw_person') }}
  where birth_year is not null
    and birth_year > 1900