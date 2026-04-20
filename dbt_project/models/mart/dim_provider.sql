{{ config(materialized='table') }}

select distinct
    provider_id,
    care_site_id
from {{ ref('stg_visit_occurrence') }}
where provider_id is not null