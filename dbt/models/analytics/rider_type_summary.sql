-- Members vs. casual riders: volume, trip length, e-bike share, weekend share, round trips.
select
    t.rider_type,
    count(*)                                                        as trips,
    round(count(*) * 100.0 / sum(count(*)) over (), 1)              as pct_of_trips,
    round(median(t.duration_min), 1)                                as median_duration_min,
    round(avg((t.rideable_type = 'electric_bike')::int) * 100, 1)   as pct_ebike,
    round(avg(d.is_weekend::int) * 100, 1)                          as pct_weekend,
    round(avg(t.is_round_trip::int) * 100, 1)                       as pct_round_trip
from {{ ref('fct_trips') }} t
join {{ ref('dim_date') }} d on d.date_day = t.trip_date
group by t.rider_type
