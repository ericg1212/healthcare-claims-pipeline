{{ config(materialized='table') }}

select
    person_id,
    birth_year,
    YEAR(CURRENT_DATE()) - birth_year           as age,
    case
        when YEAR(CURRENT_DATE()) - birth_year < 18 then '0-17'
        when YEAR(CURRENT_DATE()) - birth_year < 35 then '18-34'
        when YEAR(CURRENT_DATE()) - birth_year < 50 then '35-49'
        when YEAR(CURRENT_DATE()) - birth_year < 65 then '50-64'
        else                                              '65+'
    end                                                   as age_group,
    gender_source_value             as gender,
    race_source_value               as race
from {{ ref('stg_person') }}
