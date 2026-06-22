-- Copyright (c) 2026 Eric Grynspan. All rights reserved.
{{ config(materialized='view') }}

select
    payer_plan_period_id,
    person_id,
    payer_source_value,
    plan_source_value,
    payer_plan_period_start_date,
    payer_plan_period_end_date,
    loaded_at

from {{ source('raw', 'raw_payer_plan_period') }}
