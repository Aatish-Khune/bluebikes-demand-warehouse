-- Which stations systematically drain or fill up? Average daily net flow (arrivals - departures)
-- split by weekday/weekend, with a rank among stations that have meaningful volume.
with stats as (
    select
        f.station_id,
        f.is_weekend,
        avg(f.departures)  as avg_departures,
        avg(f.arrivals)    as avg_arrivals,
        avg(f.net_flow)    as avg_net_flow,
        count(*)           as days
    from {{ ref('fct_station_daily_demand') }} f
    group by f.station_id, f.is_weekend
)

select
    s.station_id,
    st.station_name,
    st.lat,
    st.lng,
    s.is_weekend,
    round(s.avg_departures, 2) as avg_departures,
    round(s.avg_arrivals, 2)   as avg_arrivals,
    round(s.avg_net_flow, 2)   as avg_net_flow,
    s.days,
    rank() over (partition by s.is_weekend order by s.avg_net_flow asc)  as drain_rank,
    rank() over (partition by s.is_weekend order by s.avg_net_flow desc) as fill_rank
from stats s
join {{ ref('dim_station') }} st using (station_id)
where s.avg_departures >= 5   -- ignore very quiet stations
