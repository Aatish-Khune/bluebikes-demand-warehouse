"""End-to-end: run the real dbt project (models + all data tests) on a synthetic warehouse."""

import os

import duckdb
import pytest
from fixtures import build_fixture_db

from bluebikes.config import DBT_DIR


@pytest.fixture(scope="module")
def built_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("wh") / "fixture.duckdb"
    expected = build_fixture_db(db)
    os.environ.update({"BLUEBIKES_DB": str(db), "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"})
    from dbt.cli.main import dbtRunner

    result = dbtRunner().invoke(
        ["build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    )
    assert result.success, "dbt build (models + data tests) failed on the fixture"
    return db, expected


def test_dedupes_and_filters_window(built_db):
    db, expected = built_db
    with duckdb.connect(str(db)) as con:
        n = con.execute("select count(*) from marts.fct_trips").fetchone()[0]
    assert n == expected["trips"]


def test_dst_fallback_duration_fixed(built_db):
    db, expected = built_db
    with duckdb.connect(str(db)) as con:
        minutes = con.execute("select duration_min from marts.fct_trips where ride_id = ?",
                              [expected["dst_ride_id"]]).fetchone()[0]
    assert minutes == pytest.approx(15.0)


def test_station_day_grid_is_zero_filled_and_reconciles(built_db):
    db, _ = built_db
    with duckdb.connect(str(db)) as con:
        stations = con.execute("select count(*) from marts.dim_station").fetchone()[0]
        grid_dep = con.execute(
            "select sum(departures) from marts.fct_station_daily_demand").fetchone()[0]
        trips_with_start = con.execute(
            "select count(*) from marts.fct_trips where start_station_id is not null"
        ).fetchone()[0]
        zero_days = con.execute(
            "select count(*) from marts.fct_station_daily_demand where departures = 0"
        ).fetchone()[0]
    assert stations == 3
    assert grid_dep == trips_with_start
    assert zero_days == 1  # station B2 on 2025-10-21 (fixture skips it)
