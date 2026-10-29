"""Download 12 months of Bluebikes trips + Open-Meteo daily weather, and load both into the
`raw` schema of a local DuckDB warehouse. dbt builds everything downstream of `raw`."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import duckdb
import requests

from bluebikes.config import (
    BLUEBIKES_BASE_URL,
    BOSTON_LOGAN,
    DB_PATH,
    END_DATE,
    OPEN_METEO_URL,
    RAW_DIR,
    START_DATE,
    TRIP_FILES,
    WEATHER_VARS,
)


def download(url: str, dest: Path, timeout: int = 120) -> int:
    """Stream a file to disk; skip if it already exists. Returns bytes written."""
    if dest.exists() and dest.stat().st_size > 0:
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    written = 0
    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
                written += len(chunk)
    tmp.replace(dest)
    return written


def extract_csvs(path: Path, out_dir: Path) -> list[Path]:
    """Return the trip CSV(s) for one download, unzipping if needed (skips macOS metadata)."""
    if path.suffix == ".csv":
        return [path]
    out_dir.mkdir(parents=True, exist_ok=True)
    csvs = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith(".csv") and not name.startswith("__MACOSX"):
                target = out_dir / Path(name).name
                if not target.exists():
                    zf.extract(name, out_dir)
                    extracted = out_dir / name
                    if extracted != target:
                        extracted.replace(target)
                csvs.append(target)
    return csvs


def fetch_weather() -> list[dict]:
    """Daily Boston Logan weather for the study period (one API call)."""
    params = {
        **BOSTON_LOGAN,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(WEATHER_VARS),
        "timezone": "America/New_York",
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=60)
    resp.raise_for_status()
    daily = resp.json()["daily"]
    return [
        {"date": day, **{v: daily[v][i] for v in WEATHER_VARS}}
        for i, day in enumerate(daily["time"])
    ]


def load_raw(csvs: list[Path], weather: list[dict], db_path: Path = DB_PATH) -> None:
    """(Re)create raw.trips and raw.weather. All columns are read as text in raw; types are
    cast in dbt staging so bad values surface as test failures instead of load errors."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    files = [p.as_posix() for p in csvs]
    with duckdb.connect(str(db_path)) as con:
        con.execute("create schema if not exists raw")
        con.execute(
            "create or replace table raw.trips as select * from read_csv(?, union_by_name = true,"
            " all_varchar = true, header = true, filename = true)",
            [files],
        )
        weather_json = RAW_DIR / "weather.json"
        weather_json.write_text(json.dumps(weather), encoding="utf-8")
        con.execute(
            "create or replace table raw.weather as select * from read_json_auto(?)",
            [weather_json.as_posix()],
        )
        n_trips = con.execute("select count(*) from raw.trips").fetchone()[0]
        n_days = con.execute("select count(*) from raw.weather").fetchone()[0]
    print(f"Loaded raw.trips: {n_trips:,} rows; raw.weather: {n_days} days -> {db_path}")


def main() -> None:
    csvs: list[Path] = []
    total = 0
    for name in TRIP_FILES:
        dest = RAW_DIR / "downloads" / name
        n = download(f"{BLUEBIKES_BASE_URL}/{name}", dest)
        total += n
        print(f"{'skip (exists)' if n == 0 else f'{n / 1e6:.1f} MB':>14}  {name}")
        csvs += extract_csvs(dest, RAW_DIR / "csv")
    print(f"Downloaded {total / 1e6:.0f} MB")
    load_raw(csvs, fetch_weather())


if __name__ == "__main__":
    main()
