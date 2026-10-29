-- Station locations must fall inside a generous Greater Boston bounding box.
select station_id, station_name, lat, lng
from {{ ref('dim_station') }}
where lat not between 42.0 and 42.8
   or lng not between -71.5 and -70.8
