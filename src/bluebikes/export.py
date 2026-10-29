"""Export small AGGREGATED tables for the app (committed to git and used on deploy).

Only aggregates leave the warehouse: no trip-level rows, so the raw Bluebikes data is never
redistributed (Bluebikes Data License)."""

from __future__ import annotations

import duckdb

from bluebikes.config import ARTIFACTS_DIR, DB_PATH

QUERIES = {
    "hourly_profile": "select * from analytics.hourly_demand_profile",
    "rider_summary": "select * from analytics.rider_type_summary",
    "station_imbalance": "select * from analytics.station_imbalance",
    "system_daily": """
        select f.date_day, sum(f.departures) as departures,
               any_value(f.temp_max_c) as temp_max_c, any_value(f.precip_mm) as precip_mm,
               any_value(f.is_weekend) as is_weekend
        from marts.fct_station_daily_demand f group by f.date_day order by f.date_day""",
    "monthly_top_stations": """
        select * from analytics.monthly_station_ranking where month_rank <= 10
        order by year_month, month_rank""",
}


def export_artifacts(db_path=DB_PATH) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path), read_only=True) as con:
        for name, sql in QUERIES.items():
            df = con.sql(sql).df()
            df.to_parquet(ARTIFACTS_DIR / f"{name}.parquet", index=False)
            print(f"{name:<22} {len(df):>6} rows")


if __name__ == "__main__":
    export_artifacts()
