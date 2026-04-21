{{ config(materialized='table') }}

select
    provider_id,
    min(care_site_id) as care_site_id
from {{ ref('stg_visit_occurrence') }}
where provider_id is not null
group by provider_id