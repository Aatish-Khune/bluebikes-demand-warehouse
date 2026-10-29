{{ config(severity='warn') }}
-- Trips over 24 hours are usually lost/unreturned bikes. Flag, don't fail.
select ride_id, duration_min
from {{ ref('fct_trips') }}
where duration_min > 24 * 60
