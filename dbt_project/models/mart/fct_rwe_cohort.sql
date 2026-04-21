{{ config(materialized='table') }}

with t2d as (
    select distinct person_id
    from {{ ref('stg_condition_occurrence') }}
    where condition_source_value = '44054006'
),

ckd as (
    select distinct person_id
    from {{ ref('stg_condition_occurrence') }}
    where condition_source_value in (
        '431855005',  -- CKD stage 1
        '431856006',  -- CKD stage 2
        '433144002',  -- CKD stage 3
        '431857002'   -- CKD stage 4
    )
),

metformin as (
    select distinct person_id
    from {{ ref('stg_drug_exposure') }}
    where lower(drug_display) like '%metformin%'
),

cohort as (
    select
        t2d.person_id,
        case when metformin.person_id is not null then true else false end as on_metformin
    from t2d
    inner join ckd      on t2d.person_id = ckd.person_id
    left join metformin on t2d.person_id = metformin.person_id
)

select
    c.person_id,
    c.on_metformin,
    p.age_group,
    p.gender,
    p.race
from cohort c
left join {{ ref('dim_patient') }} p on c.person_id = p.person_id
