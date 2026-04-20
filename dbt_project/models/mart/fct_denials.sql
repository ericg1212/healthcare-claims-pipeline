{{ config(materialized='table') }}

  with denials as (
      select
          claim_id,
          patient_id,
          payer_name,
          claim_type,
          submitted_amount,
          denied_amount,
          claim_date,
          case
              when procedure_display = 'Renal dialysis'  then '197'
              when payer_name = 'Medicaid'
               and claim_type = 'pharmacy'               then '96'
              else                                            '16'
          end as carc_code
      from {{ ref('stg_claim_header') }}
      where is_denied = true
  )

  select
      *,
      case
          when carc_code in ('197', '96') then 'systematic'
          else                                 'random'
      end as denial_type
  from denials