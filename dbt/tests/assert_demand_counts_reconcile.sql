-- Total departures in the daily grid must equal the number of trips with a start station.
-- Catches join fan-out or dropped rows when building the grid.
with grid as (select sum(departures) as n from {{ ref('fct_station_daily_demand') }}),
     trips as (select count(*) as n from {{ ref('fct_trips') }} where start_station_id is not null)
select grid.n as grid_departures, trips.n as trip_count
from grid, trips
where grid.n != trips.n
