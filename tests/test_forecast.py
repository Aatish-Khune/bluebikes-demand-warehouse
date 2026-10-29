import zipfile

import numpy as np
import pandas as pd
import pytest

from bluebikes.forecast import add_features, metrics, top_stations
from bluebikes.ingest import extract_csvs


def _toy(n_days=40, stations=("S1", "S2")):
    rows = []
    for s_i, s in enumerate(stations):
        for d in range(n_days):
            rows.append({
                "station_id": s, "date_day": pd.Timestamp("2026-01-01") + pd.Timedelta(days=d),
                "departures": d + 100 * s_i, "is_weekend": False, "is_holiday": False,
            })
    return pd.DataFrame(rows)


def test_lag_features_use_only_past_days():
    out = add_features(_toy())
    s1 = out[out["station_id"] == "S1"].set_index("date_day")
    day = pd.Timestamp("2026-02-05")  # departures = 35 on this day for S1
    row = s1.loc[day]
    assert row["departures"] == 35
    assert row["lag_1"] == 34 and row["lag_7"] == 28 and row["lag_14"] == 21
    assert row["roll_7"] == pytest.approx(np.mean(range(28, 35)))  # days t-7..t-1, not t
    assert row["roll_28"] == pytest.approx(np.mean(range(7, 35)))


def test_lags_never_cross_stations():
    out = add_features(_toy())
    s2_first = out[out["station_id"] == "S2"].iloc[0]
    assert s2_first["lag_1"] >= 100  # S2's own history, not S1's last day


def test_rows_without_full_history_are_dropped():
    out = add_features(_toy(n_days=40))
    assert len(out) == 2 * (40 - 28)


def test_top_stations_ignores_test_period():
    df = _toy(stations=("S1", "S2"))
    # S1 explodes only after the cutoff; selection must not see that.
    df.loc[(df.station_id == "S1") & (df.date_day >= "2026-02-01"), "departures"] = 10_000
    assert top_stations(df, 1, before="2026-02-01") == ["S2"]


def test_metrics():
    m = metrics(np.array([10, 20]), np.array([12, 16]))
    assert m["mae"] == pytest.approx(3.0)
    assert m["rmse"] == pytest.approx(np.sqrt((4 + 16) / 2))
    assert m["wape"] == pytest.approx(6 / 30)


def test_extract_csvs_skips_macos_metadata(tmp_path):
    z = tmp_path / "m.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("202601-tripdata.csv", "ride_id\nX\n")
        zf.writestr("__MACOSX/._202601-tripdata.csv", "junk")
    out = extract_csvs(z, tmp_path / "csv")
    assert [p.name for p in out] == ["202601-tripdata.csv"]
    assert out[0].read_text() == "ride_id\nX\n"
