{{ config(materialized='view') }}

select
    condition_occurrence_id,
    person_id,
    visit_occurrence_id,
    condition_source_value,
    condition_source_vocabulary,
    condition_start_datetime,
    condition_end_datetime,
    condition_display,
    loaded_at

from {{ source('raw', 'raw_condition_occurrence') }}
