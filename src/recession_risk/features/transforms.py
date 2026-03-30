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


def compute_three_month_annualized_growth(levels: pd.Series) -> pd.Series:
    prior = levels.shift(3)
    ratio = levels.divide(prior.where(prior != 0))
    return ((ratio.pow(4) - 1.0) * 100.0).where(prior.notna())


def compute_three_month_change(levels: pd.Series) -> pd.Series:
    return levels - levels.shift(3)


def compute_three_month_growth(levels: pd.Series) -> pd.Series:
    prior = levels.shift(3)
    ratio = levels.divide(prior.where(prior != 0))
    return ((ratio - 1.0) * 100.0).where(prior.notna())


def compute_drawdown(levels: pd.Series, window: int) -> pd.Series:
    rolling_peak = levels.rolling(window=window, min_periods=1).max()
    return ((rolling_peak - levels).divide(rolling_peak.where(rolling_peak != 0)) * 100.0).clip(lower=0.0)


def apply_configured_feature_transforms(panel: pd.DataFrame, series_specs: dict[str, dict]) -> pd.DataFrame:
    transformed = panel.copy()
    for series_id, spec in series_specs.items():
        if series_id not in transformed.columns:
            continue
        transform = str(spec.get("transform", "level"))
        feature_name = str(spec.get("feature_name", series_id))
        series = pd.to_numeric(transformed[series_id], errors="coerce")

        if transform == "level":
            if feature_name != series_id:
                transformed[feature_name] = series
            continue

        if transform == "growth_3m_annualized":
            transformed[feature_name] = compute_three_month_annualized_growth(series)
            continue

        if transform == "change_3m":
            transformed[feature_name] = compute_three_month_change(series)
            continue

        if transform == "growth_3m":
            transformed[feature_name] = compute_three_month_growth(series)
            continue

        if transform.startswith("drawdown_") and transform.endswith("m"):
            window = int(transform.split("_")[1].replace("m", ""))
            transformed[feature_name] = compute_drawdown(series, window=window)
            continue

        raise ValueError(f"Unsupported configured transform for {series_id}: {transform}")

    return transformed
