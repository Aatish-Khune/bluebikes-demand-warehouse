-- Average trips per hour on weekdays vs. weekends, by rider type (commute peaks vs. leisure).
with hourly as (
    select t.trip_date, t.start_hour, t.rider_type, d.is_weekend, count(*) as trips
    from {{ ref('fct_trips') }} t
    join {{ ref('dim_date') }} d on d.date_day = t.trip_date
    group by all
),

n_days as (
    select is_weekend, count(*) as days from {{ ref('dim_date') }} group by all
)

select
    h.is_weekend,
    h.start_hour,
    h.rider_type,
    sum(h.trips) * 1.0 / any_value(n.days) as avg_trips_per_day
from hourly h
join n_days n using (is_weekend)
group by h.is_weekend, h.start_hour, h.rider_type
order by h.is_weekend, h.rider_type, h.start_hour
