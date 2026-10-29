-- One row per station seen as a trip START in the window. Name = most frequent name used;
-- location = median of reported start coordinates (robust to GPS noise on e-bike trips).
with starts as (
    select start_station_id as station_id, start_station_name as station_name,
           start_lat as lat, start_lng as lng, trip_date
    from {{ ref('stg_trips') }}
    where start_station_id is not null
),

names as (
    select station_id, station_name,
           row_number() over (partition by station_id order by count(*) desc, station_name) as rn
    from starts
    group by station_id, station_name
)

select
    s.station_id,
    n.station_name,
    median(s.lat)        as lat,
    median(s.lng)        as lng,
    min(s.trip_date)     as first_trip_date,
    max(s.trip_date)     as last_trip_date,
    count(*)             as total_departures
from starts s
join names n on n.station_id = s.station_id and n.rn = 1
group by s.station_id, n.station_name
