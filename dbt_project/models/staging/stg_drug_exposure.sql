{{ config(materialized='view') }}

select
    drug_exposure_id,
    person_id,
    visit_occurrence_id,
    drug_source_value,
    drug_source_vocabulary,
    drug_display,
    drug_exposure_start_datetime,
    drug_exposure_end_datetime,
    quantity,
    days_supply,
    loaded_at

from {{ source('raw', 'raw_drug_exposure') }}
