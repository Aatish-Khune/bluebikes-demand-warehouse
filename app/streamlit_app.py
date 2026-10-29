"""Streamlit dashboard for the Bluebikes demand warehouse and forecast.

Uses only the small aggregated tables in artifacts/ and reports/ (no trip-level data).
Run locally with `python run.py app`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
ART, REP = ROOT / "artifacts", ROOT / "reports"

st.set_page_config(page_title="Boston Bluebikes Demand", layout="wide")


@st.cache_data
def load():
    t = {p.stem: pd.read_parquet(p) for p in ART.glob("*.parquet")}
    t["forecast_metrics"] = pd.read_csv(REP / "forecast_metrics.csv")
    t["forecast_by_station"] = pd.read_csv(REP / "forecast_by_station.csv")
    return t


T = load()
daily, riders = T["system_daily"], T["rider_summary"]

st.title("Boston Bluebikes: demand warehouse & station forecast")
st.caption(
    "12 months of trips (Oct 2025 – Sep 2026) modeled with dbt + DuckDB. Independent student "
    "project, not affiliated with or endorsed by Bluebikes, Lyft, or any municipality. "
    "Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0)."
)

# Render only the selected section: charts (especially maps) drawn inside hidden st.tabs
# initialize at zero size and don't render.
section = st.radio("Section", ["System overview", "Station imbalance & rebalancing",
                               "Demand forecast"], horizontal=True, label_visibility="collapsed")

if section == "System overview":
    total = int(riders["trips"].sum())
    member = riders.set_index("rider_type").loc["member"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trips", f"{total / 1e6:.2f}M")
    c2.metric("Busiest day", f"{int(daily['departures'].max()):,} trips")
    c3.metric("Member share", f"{member['pct_of_trips']:.1f}%")
    c4.metric("Median member trip", f"{member['median_duration_min']:.1f} min")

    fig = go.Figure()
    fig.add_bar(x=daily["date_day"], y=daily["departures"], name="Daily trips",
                marker_color="#1f77b4", opacity=0.6)
    fig.add_scatter(x=daily["date_day"], y=daily["temp_max_c"], name="Max temp (°C)",
                    yaxis="y2", line=dict(color="#d62728", width=1.5))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                      yaxis=dict(title="Trips per day"),
                      yaxis2=dict(title="°C", overlaying="y", side="right"),
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

    hp = T["hourly_profile"].copy()
    hp["day_type"] = hp["is_weekend"].map({True: "Weekend", False: "Weekday"})
    fig = px.line(hp, x="start_hour", y="avg_trips_per_day", color="rider_type",
                  facet_col="day_type", markers=True,
                  labels={"start_hour": "Hour of day", "avg_trips_per_day": "Avg trips / day",
                          "rider_type": "Rider"})
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
    st.subheader("When do people ride?")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(riders, hide_index=True, use_container_width=True)

elif section == "Station imbalance & rebalancing":
    weekend = st.radio("Day type", ["Weekday", "Weekend"], horizontal=True) == "Weekend"
    imb = T["station_imbalance"]
    imb = imb[imb["is_weekend"] == weekend].copy()
    imb["size"] = imb["avg_departures"].clip(lower=5)
    st.markdown(
        "Average daily **net flow** = arrivals − departures. Red stations **lose bikes** "
        "(need refills); blue stations **fill up** (need bikes removed)."
    )
    lim = float(imb["avg_net_flow"].abs().quantile(0.98))
    # Plain lat/lng scatter instead of a tile map: no WebGL2 or external tile server needed,
    # so it renders in every browser.
    fig = px.scatter(
        imb, x="lng", y="lat", color="avg_net_flow", size="size",
        color_continuous_scale="RdBu", range_color=(-lim, lim),
        hover_name="station_name",
        hover_data={"avg_net_flow": ":.1f", "avg_departures": ":.0f", "lat": False,
                    "lng": False, "size": False},
        labels={"avg_net_flow": "Net flow / day"}, height=560,
    )
    # 1 degree of latitude spans ~1.35x the distance of 1 degree of longitude at Boston.
    # Zoom to where 99% of stations are, so a few outlying stations don't shrink the view.
    lo, hi = imb[["lng", "lat"]].quantile(0.005), imb[["lng", "lat"]].quantile(0.995)
    pad = 0.01
    fig.update_xaxes(range=[lo["lng"] - pad, hi["lng"] + pad], title=None,
                     showticklabels=False, showgrid=False)
    fig.update_yaxes(range=[lo["lat"] - pad, hi["lat"] + pad], scaleanchor="x",
                     scaleratio=1.35, title=None, showticklabels=False, showgrid=False)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

    cols = ["station_name", "avg_net_flow", "avg_departures", "avg_arrivals"]
    left, right = st.columns(2)
    left.markdown("**Rebalancing watchlist: stations that drain** (bring bikes in)")
    left.dataframe(imb.nsmallest(10, "avg_net_flow")[cols], hide_index=True,
                   use_container_width=True)
    right.markdown("**Stations that fill up** (take bikes out)")
    right.dataframe(imb.nlargest(10, "avg_net_flow")[cols], hide_index=True,
                    use_container_width=True)

else:
    st.markdown(
        "Next-day departures for the 20 busiest stations. Test period **Aug 1 – Sep 30, 2026** "
        "was never used for training or early stopping."
    )
    st.dataframe(T["forecast_metrics"], hide_index=True, use_container_width=True)
    st.info(
        "The full LightGBM model uses the *observed* weather of the forecast day as a stand-in "
        "for a weather forecast, so its gain is an upper bound. The no-weather model's gain "
        "is what's achievable without any weather information."
    )
    fc = T["forecast_test"]
    names = fc.groupby("station_name")["departures"].mean().sort_values(ascending=False)
    station = st.selectbox("Station", names.index)
    s = fc[fc["station_name"] == station]
    fig = go.Figure()
    fig.add_scatter(x=s["date_day"], y=s["departures"], name="Actual",
                    line=dict(color="#ff7f0e", width=2))
    fig.add_scatter(x=s["date_day"], y=s["pred_seasonal_naive"], name="Seasonal naive",
                    line=dict(color="#aaa", dash="dot"))
    fig.add_scatter(x=s["date_day"], y=s["pred_lgbm"], name="LightGBM",
                    line=dict(color="#2ca02c"))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                      yaxis_title="Departures / day", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("**Error by station (MAE, trips/day)**")
    st.dataframe(T["forecast_by_station"].drop(columns="station_id"), hide_index=True,
                 use_container_width=True)
