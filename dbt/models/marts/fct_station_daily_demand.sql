-- Station x day grid with ZERO-FILLED departures/arrivals for every day between a station's
-- first and last trip. Missing days would otherwise look like "no data" instead of "no demand",
-- which biases any forecast trained on this table.
with departures as (
    select start_station_id as station_id, trip_date as date_day, count(*) as departures,
           sum((rider_type = 'member')::int) as member_departures
    from {{ ref('fct_trips') }}
    where start_station_id is not null
    group by all
),

arrivals as (
    select end_station_id as station_id, cast(ended_at as date) as date_day, count(*) as arrivals
    from {{ ref('fct_trips') }}
    where end_station_id is not null
    group by all
),

grid as (
    select s.station_id, d.date_day
    from {{ ref('dim_station') }} s
    join {{ ref('dim_date') }} d
      on d.date_day between s.first_trip_date and s.last_trip_date
)

select
    g.station_id,
    g.date_day,
    coalesce(dep.departures, 0)                                  as departures,
    coalesce(dep.member_departures, 0)                           as member_departures,
    coalesce(arr.arrivals, 0)                                    as arrivals,
    coalesce(arr.arrivals, 0) - coalesce(dep.departures, 0)      as net_flow,  -- < 0: drains bikes
    dd.iso_dow,
    dd.is_weekend,
    dd.is_holiday,
    dd.month_num,
    w.temp_max_c,
    w.temp_min_c,
    w.precip_mm,
    w.snowfall_cm,
    w.wind_max_kmh
from grid g
left join departures dep on dep.station_id = g.station_id and dep.date_day = g.date_day
left join arrivals arr on arr.station_id = g.station_id and arr.date_day = g.date_day
join {{ ref('dim_date') }} dd on dd.date_day = g.date_day
left join {{ ref('stg_weather') }} w on w.weather_date = g.date_day
