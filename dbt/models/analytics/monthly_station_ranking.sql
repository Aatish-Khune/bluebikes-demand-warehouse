-- Monthly departures per station with rank, month-over-month change, and running total
-- (window functions: dense_rank, lag, cumulative sum).
with monthly as (
    select station_id, strftime(date_day, '%Y-%m') as year_month, sum(departures) as departures
    from {{ ref('fct_station_daily_demand') }}
    group by all
)

select
    m.year_month,
    m.station_id,
    st.station_name,
    m.departures,
    dense_rank() over (partition by m.year_month order by m.departures desc)       as month_rank,
    m.departures - lag(m.departures) over (partition by m.station_id order by m.year_month)
                                                                                    as mom_change,
    sum(m.departures) over (partition by m.station_id order by m.year_month
                            rows between unbounded preceding and current row)      as running_total
from monthly m
join {{ ref('dim_station') }} st using (station_id)
