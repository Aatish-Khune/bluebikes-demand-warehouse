-- Trip-grain fact table. Station keys can be NULL (dockless e-bike starts/ends).
select
    ride_id,
    trip_date,
    start_hour,
    started_at,
    ended_at,
    start_station_id,
    end_station_id,
    rideable_type,
    rider_type,
    duration_min,
    is_round_trip
from {{ ref('stg_trips') }}
