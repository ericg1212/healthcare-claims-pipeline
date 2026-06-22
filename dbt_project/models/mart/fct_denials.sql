-- Copyright (c) 2026 Eric Grynspan. All rights reserved.
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
        procedure_display
    from {{ ref('stg_claim_header') }}
    where is_denied = true
),

rules as (select * from {{ ref('denial_rules') }}),

-- Rule 1: procedure match (highest priority)
proc_match as (
    select d.claim_id, r.carc_code, r.denial_type
    from denials d
    inner join rules r
        on d.procedure_display = r.match_procedure
        and r.match_procedure is not null and r.match_procedure != ''
),

-- Rule 2: payer + claim_type match
payer_match as (
    select d.claim_id, r.carc_code, r.denial_type
    from denials d
    inner join rules r
        on d.payer_name  = r.match_payer_name
        and d.claim_type = r.match_claim_type
        and r.match_payer_name is not null and r.match_payer_name != ''
),

attributed as (
    select
        d.*,
        coalesce(pm.carc_code,  pam.carc_code,  '16')      as carc_code,
        coalesce(pm.denial_type, pam.denial_type, 'random') as denial_type
    from denials d
    left join proc_match  pm  on d.claim_id = pm.claim_id
    left join payer_match pam on d.claim_id = pam.claim_id
),

joined as (
    select
        a.*,
        dt.year
    from attributed a
    left join {{ ref('dim_date') }} dt on a.claim_date = dt.date_day
)

select * from joined
