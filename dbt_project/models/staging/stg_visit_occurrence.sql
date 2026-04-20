{{ config(materialized='view') }}

select
    visit_occurrence_id,
    person_id,
    visit_start_datetime,
    visit_end_datetime,
    visit_type_source_value,
    provider_id,
    care_site_id,
    loaded_at

from {{ source('raw', 'raw_visit_occurrence') }}
