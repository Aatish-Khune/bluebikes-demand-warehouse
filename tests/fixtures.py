"""Tiny synthetic raw warehouse for CI: same schema as the real Bluebikes files, but made-up
rows (no real data is committed). Includes the edge cases the dbt models must handle."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

STATIONS = {
    "A1": ("Test Station A", 42.35, -71.06),
    "B2": ("Test Station B", 42.36, -71.09),
    "C3": ("Test Station C", 42.37, -71.11),
}


def _trip(i: int, start: datetime, minutes: float, s_from: str, s_to: str | None,
          rider: str = "member", bike: str = "classic_bike", end: datetime | None = None) -> dict:
    a, b = STATIONS[s_from], STATIONS[s_to] if s_to else (None, None, None)
    end = end or start + timedelta(minutes=minutes)
    return {
        "ride_id": f"R{i:05d}", "rideable_type": bike,
        "started_at": start.strftime("%Y-%m-%d %H:%M:%S.000"),
        "ended_at": end.strftime("%Y-%m-%d %H:%M:%S.000"),
        "start_station_name": a[0], "start_station_id": s_from,
        "end_station_name": b[0], "end_station_id": s_to,
        "start_lat": str(a[1]), "start_lng": str(a[2]),
        "end_lat": str(b[1]) if b[1] else None, "end_lng": str(b[2]) if b[2] else None,
        "member_casual": rider, "filename": "fixture.csv",
    }


def build_fixture_db(path: Path) -> dict:
    """Create raw.trips / raw.weather. Returns the expected counts for assertions."""
    trips, i = [], 0
    day = date(2025, 10, 1)
    for d in range(45):  # 2025-10-01 .. 2025-11-14
        for hour, (s_from, s_to) in enumerate([("A1", "B2"), ("B2", "C3"), ("A1", "C3")]):
            if d == 20 and s_from == "B2":
                continue  # B2 has a zero-departure day mid-period -> grid must zero-fill it
            start = datetime.combine(day + timedelta(days=d), datetime.min.time()) + timedelta(
                hours=8 + hour)
            trips.append(_trip(i, start, 12, s_from, s_to,
                               rider="casual" if d % 3 == 0 else "member"))
            i += 1
    # Edge case 1: duplicate ride_id (appears in two monthly files upstream).
    trips.append(dict(trips[0]))
    # Edge case 2: DST fall-back -- starts 01:50 EDT, ends 01:05 EST (15 real minutes).
    trips.append(_trip(i, datetime(2025, 11, 2, 1, 50), 0, "A1", "B2",
                       end=datetime(2025, 11, 2, 1, 5)))
    i += 1
    # Edge case 3: dockless e-bike end (no end station).
    trips.append(_trip(i, datetime(2025, 10, 5, 18, 0), 20, "C3", None, bike="electric_bike"))
    # Edge case 4: started before the study window (should be filtered out).
    trips.append(_trip(i + 1, datetime(2025, 9, 30, 23, 50), 15, "A1", "B2"))

    weather = [
        {"date": (date(2025, 10, 1) + timedelta(days=k)).isoformat(),
         "temperature_2m_max": 15.0, "temperature_2m_min": 5.0, "precipitation_sum": 0.0,
         "snowfall_sum": 0.0, "wind_speed_10m_max": 10.0}
        for k in range(365)
    ]
    cols = list(trips[0])
    with duckdb.connect(str(path)) as con:
        con.execute("create schema raw")
        con.execute("create table raw.trips (" + ", ".join(f"{c} varchar" for c in cols) + ")")
        con.executemany(f"insert into raw.trips values ({', '.join('?' * len(cols))})",
                        [[t[c] for c in cols] for t in trips])
        con.execute("create table raw.weather (date date, temperature_2m_max double, "
                    "temperature_2m_min double, precipitation_sum double, snowfall_sum double, "
                    "wind_speed_10m_max double)")
        con.executemany("insert into raw.weather values (?, ?, ?, ?, ?, ?)",
                        [list(w.values()) for w in weather])
    # 134 regular + DST trip + dockless trip; duplicate and pre-window rows removed.
    return {"trips": 134 + 2, "stations": 3, "dst_ride_id": f"R{i - 1:05d}"}
