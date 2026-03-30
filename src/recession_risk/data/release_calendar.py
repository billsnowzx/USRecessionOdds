from __future__ import annotations

import pandas as pd


def get_available_date(series_spec: dict, observation_date: str | pd.Timestamp) -> pd.Timestamp:
    observation_ts = pd.Timestamp(observation_date).to_period("M").to_timestamp()
    frequency = series_spec.get("frequency", "monthly")
    lag_months = int(series_spec.get("release_lag_months", 0))
    lag_days = int(series_spec.get("release_lag_days", 0))

    if frequency == "daily":
        available = observation_ts + pd.offsets.MonthEnd(0)
    else:
        available = observation_ts + pd.offsets.MonthEnd(0)

    available += pd.DateOffset(months=lag_months, days=lag_days)
    return pd.Timestamp(available).normalize()


def is_observation_available(series_spec: dict, observation_date: str | pd.Timestamp, as_of_date: str | pd.Timestamp) -> bool:
    return get_available_date(series_spec, observation_date) <= pd.Timestamp(as_of_date).normalize()
