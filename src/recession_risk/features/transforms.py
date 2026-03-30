from __future__ import annotations

from pathlib import Path

import pandas as pd

DATE_COLUMNS = ["DATE", "observation_date"]
VALUE_COLUMNS = ["VALUE"]


def load_fred_csv(path: str | Path, series_id: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = next((column for column in DATE_COLUMNS if column in frame.columns), None)
    value_column = next((column for column in [series_id, *VALUE_COLUMNS] if column in frame.columns), None)
    if date_column is None or value_column is None:
        raise ValueError(f"Unexpected FRED file format for {series_id}: {path}")
    frame = frame.rename(columns={date_column: "date", value_column: series_id})
    frame["date"] = pd.to_datetime(frame["date"])
    frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce")
    return frame[["date", series_id]].dropna()


def aggregate_to_monthly(frame: pd.DataFrame, value_column: str, method: str) -> pd.Series:
    monthly = frame.copy()
    monthly["month"] = monthly["date"].dt.to_period("M").dt.to_timestamp()
    grouped = monthly.groupby("month")[value_column]
    if method == "mean":
        result = grouped.mean()
    elif method == "eom":
        result = grouped.last()
    else:
        raise ValueError(f"Unsupported aggregation method: {method}")
    result.name = value_column
    return result.sort_index()


def combine_monthly_series(series_map: dict[str, pd.Series]) -> pd.DataFrame:
    panel = pd.concat(series_map.values(), axis=1, join="outer").sort_index()
    panel.index.name = "date"
    return panel.reset_index()


def compute_term_spread(panel: pd.DataFrame) -> pd.Series:
    return panel["DGS10"] - panel["DTB3"]


def compute_sahm_gap(unemployment: pd.Series) -> pd.Series:
    three_month_avg = unemployment.rolling(window=3, min_periods=3).mean()
    rolling_min = three_month_avg.rolling(window=12, min_periods=1).min()
    return three_month_avg - rolling_min