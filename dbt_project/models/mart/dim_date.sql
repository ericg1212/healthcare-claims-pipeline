{{ config(materialized='table') }}

  with date_spine as (
      select
          dateadd(day, seq4(), '2020-01-01'::date) as date_day
      from table(generator(rowcount => 3653))
  )

  select
      date_day,
      year(date_day)                          as year,
      month(date_day)                         as month,
      day(date_day)                           as day,
      quarter(date_day)                       as quarter,
      dayofweek(date_day)                     as day_of_week,
      dayname(date_day)                       as day_name,
      monthname(date_day)                     as month_name,
      case when dayofweek(date_day) in (0, 6) then true else false end as
  is_weekend,
      to_char(date_day, 'YYYY-MM')            as year_month
  from date_spine