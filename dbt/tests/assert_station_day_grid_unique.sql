-- The demand grid must have exactly one row per station per day.
select station_id, date_day, count(*) as n
from {{ ref('fct_station_daily_demand') }}
group by station_id, date_day
having count(*) > 1
