"""Next-day departures forecast for the busiest stations.

- Baseline: seasonal naive (same weekday last week = lag 7).
- Model: one global LightGBM across stations, with lags, rolling means, calendar, and weather.
- Split by time: test = Aug-Sep 2026 (never seen in training or early stopping).
"""

from __future__ import annotations

import json

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd

from bluebikes.config import (
    ARTIFACTS_DIR,
    DB_PATH,
    N_TOP_STATIONS,
    REPORTS_DIR,
    SEED,
    TEST_START,
    VAL_DAYS,
)

TARGET = "departures"
CALENDAR = ["iso_dow", "is_weekend", "is_holiday", "month_num"]
WEATHER = ["temp_max_c", "temp_min_c", "precip_mm", "snowfall_cm", "wind_max_kmh"]
LAGS = ["lag_1", "lag_7", "lag_14", "roll_7", "roll_28"]


def load_demand(db_path=DB_PATH) -> pd.DataFrame:
    with duckdb.connect(str(db_path), read_only=True) as con:
        df = con.sql(
            "select f.*, s.station_name from marts.fct_station_daily_demand f "
            "join marts.dim_station s using (station_id)"
        ).df()
    df["date_day"] = pd.to_datetime(df["date_day"])
    return df.sort_values(["station_id", "date_day"]).reset_index(drop=True)


def top_stations(df: pd.DataFrame, n: int, before: str) -> list[str]:
    """Busiest stations measured on TRAINING dates only (avoids test-period selection leak)."""
    train = df[df["date_day"] < pd.Timestamp(before)]
    return train.groupby("station_id")[TARGET].sum().nlargest(n).index.tolist()


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Lag/rolling features per station. Every feature for day t uses departures up to t-1."""
    df = df.sort_values(["station_id", "date_day"]).copy()
    g = df.groupby("station_id")[TARGET]
    df["lag_1"] = g.shift(1)
    df["lag_7"] = g.shift(7)
    df["lag_14"] = g.shift(14)
    df["roll_7"] = g.transform(lambda s: s.shift(1).rolling(7).mean())
    df["roll_28"] = g.transform(lambda s: s.shift(1).rolling(28).mean())
    df["station_code"] = df["station_id"].astype("category")
    for col in ("is_weekend", "is_holiday"):
        df[col] = df[col].astype(int)
    return df.dropna(subset=LAGS).reset_index(drop=True)


def metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    err = np.asarray(pred, float) - np.asarray(y, float)
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "wape": float(np.sum(np.abs(err)) / np.sum(np.abs(y))),  # weighted abs % error
    }


def fit_lgbm(train: pd.DataFrame, val: pd.DataFrame, features: list[str]) -> lgb.LGBMRegressor:
    """Fit with early stopping on the validation window, then refit train+val at that size."""
    params = dict(
        n_estimators=2000, learning_rate=0.03, num_leaves=31, min_child_samples=20,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=SEED,
        objective="poisson", verbose=-1,  # Poisson suits non-negative counts
    )
    probe = lgb.LGBMRegressor(**params)
    probe.fit(train[features], train[TARGET], eval_X=val[features], eval_y=val[TARGET],
              callbacks=[lgb.early_stopping(100, verbose=False)])
    best = probe.best_iteration_ or params["n_estimators"]
    full = pd.concat([train, val])
    model = lgb.LGBMRegressor(**{**params, "n_estimators": best})
    model.fit(full[features], full[TARGET])
    return model


def run_forecast() -> pd.DataFrame:
    df = load_demand()
    stations = top_stations(df, N_TOP_STATIONS, TEST_START)
    data = add_features(df[df["station_id"].isin(stations)])

    test_start = pd.Timestamp(TEST_START)
    val_start = test_start - pd.Timedelta(days=VAL_DAYS)
    train = data[data["date_day"] < val_start]
    val = data[(data["date_day"] >= val_start) & (data["date_day"] < test_start)]
    test = data[data["date_day"] >= test_start].copy()

    full_feats = ["station_code", *CALENDAR, *LAGS, *WEATHER]
    no_weather = ["station_code", *CALENDAR, *LAGS]
    model = fit_lgbm(train, val, full_feats)
    model_nw = fit_lgbm(train, val, no_weather)

    test["pred_seasonal_naive"] = test["lag_7"]
    test["pred_naive_lag1"] = test["lag_1"]
    test["pred_lgbm"] = model.predict(test[full_feats])
    test["pred_lgbm_no_weather"] = model_nw.predict(test[no_weather])

    rows = []
    for name, col in [("seasonal_naive (lag 7)", "pred_seasonal_naive"),
                      ("naive (yesterday)", "pred_naive_lag1"),
                      ("lightgbm_no_weather", "pred_lgbm_no_weather"),
                      ("lightgbm", "pred_lgbm")]:
        rows.append({"model": name, **metrics(test[TARGET].to_numpy(), test[col].to_numpy())})
    results = pd.DataFrame(rows)
    base = results.loc[results["model"] == "seasonal_naive (lag 7)", "mae"].item()
    results["mae_vs_seasonal_naive_pct"] = (100 * (base - results["mae"]) / base).round(1)
    results[["mae", "rmse", "wape"]] = results[["mae", "rmse", "wape"]].round(3)

    by_station = (
        test.groupby(["station_id", "station_name"])
        .apply(lambda g: pd.Series({
            "mean_departures": g[TARGET].mean(),
            "mae_seasonal_naive": np.mean(np.abs(g["pred_seasonal_naive"] - g[TARGET])),
            "mae_lightgbm": np.mean(np.abs(g["pred_lgbm"] - g[TARGET])),
        }), include_groups=False)
        .round(2).reset_index()
    )
    importance = (
        pd.DataFrame({"feature": full_feats,
                      "gain": model.booster_.feature_importance(importance_type="gain")})
        .assign(share=lambda d: (d["gain"] / d["gain"].sum()).round(3))
        .sort_values("gain", ascending=False)[["feature", "share"]]
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(REPORTS_DIR / "forecast_metrics.csv", index=False)
    by_station.to_csv(REPORTS_DIR / "forecast_by_station.csv", index=False)
    importance.to_csv(REPORTS_DIR / "feature_importance.csv", index=False)
    test[["station_id", "station_name", "date_day", TARGET, "pred_seasonal_naive",
          "pred_lgbm"]].to_parquet(ARTIFACTS_DIR / "forecast_test.parquet", index=False)
    with open(REPORTS_DIR / "forecast_info.json", "w", encoding="utf-8") as fh:
        json.dump({
            "stations": len(stations), "train_rows": len(train), "val_rows": len(val),
            "test_rows": len(test), "test_start": TEST_START,
            "test_end": str(test["date_day"].max().date()),
            "best_iterations": {"lightgbm": model.n_estimators,
                                "lightgbm_no_weather": model_nw.n_estimators},
        }, fh, indent=2)
    print(results.to_string(index=False))
    print(importance.head(8).to_string(index=False))
    return results


if __name__ == "__main__":
    run_forecast()
