{{ config(materialized='view') }}

select
      claim_id,
      patient_id,
      payer_id, 
      payer_name,
      claim_type,
      submitted_amount,
      payment_amount,
       submitted_amount - payment_amount        as denied_amount,
  case
      when payer_name != 'NO_INSURANCE'
       and payment_amount = 0
       and submitted_amount > 0
      then true
      else false
  end                                      as is_denied,
    claim_date,
    procedure_display,
    loaded_at
  from {{ source('raw', 'raw_claim_header') }}
  where claim_date is not null