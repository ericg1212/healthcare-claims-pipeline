{{ config(materialized='table') }}

with condition_codes as (select * from {{ ref('condition_codes') }}),

t2d as (
    select distinct c.person_id
    from {{ ref('stg_condition_occurrence') }} c
    inner join condition_codes cc
        on c.condition_source_value = cc.snomed_code
    where cc.cohort_flag = 't2d'
),

ckd as (
    select distinct c.person_id
    from {{ ref('stg_condition_occurrence') }} c
    inner join condition_codes cc
        on c.condition_source_value = cc.snomed_code
    where cc.cohort_flag = 'ckd'
),

metformin as (
    select distinct person_id
    from {{ ref('stg_drug_exposure') }}
    where drug_source_value in (
        '860975',   -- metformin hydrochloride 500 MG Oral Tablet
        '861004',   -- metformin hydrochloride 850 MG Oral Tablet
        '861007',   -- metformin hydrochloride 1000 MG Oral Tablet
        '1807894'   -- 24 HR metformin hydrochloride 500 MG Extended Release Oral Tablet
    )
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
