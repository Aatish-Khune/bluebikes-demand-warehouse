"""Paths, data sources, and modeling settings."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Raw downloads + DuckDB warehouse (gitignored: the data license forbids redistribution)
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.environ.get("BLUEBIKES_DB", DATA_DIR / "warehouse.duckdb"))
DBT_DIR = ROOT / "dbt"
ARTIFACTS_DIR = ROOT / "artifacts"  # small AGGREGATED tables for the app (committed)
REPORTS_DIR = ROOT / "reports"

SEED = 42

# Bluebikes trip history: official public bucket linked from bluebikes.com/system-data.
# Bluebikes Data License: analysis OK; no redistribution of the raw data.
BLUEBIKES_BASE_URL = "https://s3.amazonaws.com/hubway-data"
# Last 12 complete months available (file names are not fully consistent upstream).
TRIP_FILES = [
    "202510-bluebikes-tripdata.zip",
    "202511-bluebikes-tripdata.csv.zip",
    "202512-bluebikes-tripdata.zip",
    "202601-bluebikes-tripdata.zip",
    "202602-bluebikes-tripdata.zip",
    "202603-bluebikes-tripdata.zip",
    "202604-bluebikes-tripdata.zip",
    "202605-bluebikes-tripdata.zip",
    "202606-bluebikes-tripdata.zip",
    "202607-bluebikes-tripdata.zip",
    "202608-bluebikes-tripdata.zip",
    "202609-bluebikes-tripdata.csv",
]
START_DATE = "2025-10-01"
END_DATE = "2026-09-30"

# Weather: Open-Meteo historical archive (CC BY 4.0, free for non-commercial use, no key).
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
BOSTON_LOGAN = {"latitude": 42.3656, "longitude": -71.0096}
WEATHER_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "snowfall_sum",
    "wind_speed_10m_max",
]

# Forecasting
N_TOP_STATIONS = 20
TEST_START = "2026-08-01"  # last 2 months held out (time-based split)
VAL_DAYS = 30  # last 30 days of training used for LightGBM early stopping


def dbt_env() -> dict[str, str]:
    """Environment for dbt: config and outputs stay inside the project, no telemetry."""
    env = dict(os.environ)
    env.update(
        {
            "DBT_PROFILES_DIR": str(DBT_DIR),
            "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
            "BLUEBIKES_DB": str(DB_PATH),
        }
    )
    return env
