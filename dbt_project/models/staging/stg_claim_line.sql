-- Copyright (c) 2026 Eric Grynspan. All rights reserved.
{{ config(materialized='view') }}

select
    claim_line_id,
    claim_id,
    sequence,
    procedure_code,
    procedure_display,
    quantity,
    submitted_amount,
    payment_amount,
    round(submitted_amount - payment_amount, 2) as denied_amount,
    case
        when payment_amount = 0 and submitted_amount > 0 then true
        else false
    end                                           as is_denied_line,
    loaded_at

from {{ source('raw', 'raw_claim_line') }}