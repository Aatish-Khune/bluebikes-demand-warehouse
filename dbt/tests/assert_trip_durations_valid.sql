-- Trips must not end before they start. (Very long trips are legitimate edge cases and are
-- monitored by the warn-level test below, not failed.)
select ride_id, started_at, ended_at, duration_min
from {{ ref('fct_trips') }}
where duration_min < 0
