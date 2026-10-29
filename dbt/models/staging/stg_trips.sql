-- One row per trip: typed, deduplicated, and restricted to the study window.
with typed as (
    select
        ride_id,
        rideable_type,
        member_casual                              as rider_type,
        try_cast(started_at as timestamp)          as started_at,
        try_cast(ended_at as timestamp)            as ended_at,
        nullif(trim(start_station_id), '')         as start_station_id,
        nullif(trim(start_station_name), '')       as start_station_name,
        nullif(trim(end_station_id), '')           as end_station_id,
        nullif(trim(end_station_name), '')         as end_station_name,
        try_cast(start_lat as double)              as start_lat,
        try_cast(start_lng as double)              as start_lng,
        try_cast(end_lat as double)                as end_lat,
        try_cast(end_lng as double)                as end_lng
    from {{ source('raw', 'trips') }}
),

deduped as (
    -- A handful of ride_ids appear twice across monthly files; keep one copy.
    select *
    from typed
    qualify row_number() over (partition by ride_id order by started_at) = 1
)

select
    *,
    cast(started_at as date)                                   as trip_date,
    hour(started_at)                                           as start_hour,
    -- Timestamps are local time without a time zone. When clocks fall back (1-2 AM repeats),
    -- a trip can appear to end before it starts; add back the repeated hour in that case only.
    case
        when date_diff('second', started_at, ended_at) < 0
             and cast(started_at as date) in ({% for d in var("dst_fallback_dates") %}date '{{ d }}'{% if not loop.last %}, {% endif %}{% endfor %})
             and hour(started_at) = 1
        then date_diff('second', started_at, ended_at) / 60.0 + 60
        else date_diff('second', started_at, ended_at) / 60.0
    end                                                        as duration_min,
    start_station_id is not null and start_station_id = end_station_id as is_round_trip
from deduped
where started_at is not null
  and ended_at is not null
  and cast(started_at as date) between date '{{ var("start_date") }}' and date '{{ var("end_date") }}'
