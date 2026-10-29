with days as (
    select cast(d as date) as date_day
    from range(date '{{ var("start_date") }}', date '{{ var("end_date") }}' + interval 1 day,
               interval 1 day) t(d)
)

select
    d.date_day,
    isodow(d.date_day)                       as iso_dow,      -- 1 = Monday ... 7 = Sunday
    dayname(d.date_day)                      as day_name,
    isodow(d.date_day) >= 6                  as is_weekend,
    h.holiday_name is not null               as is_holiday,
    h.holiday_name,
    month(d.date_day)                        as month_num,
    strftime(d.date_day, '%Y-%m')            as year_month,
    case when month(d.date_day) in (12, 1, 2) then 'winter'
         when month(d.date_day) in (3, 4, 5) then 'spring'
         when month(d.date_day) in (6, 7, 8) then 'summer'
         else 'fall' end                     as season
from days d
left join {{ ref('holidays') }} h on h.holiday_date = d.date_day
