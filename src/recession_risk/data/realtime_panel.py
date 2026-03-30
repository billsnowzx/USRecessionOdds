from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from recession_risk.data.registry import get_series_spec
from recession_risk.data.release_calendar import get_available_date
from recession_risk.data.vintages import get_series_asof, load_vintage_frame
from recession_risk.features.labels import build_recession_start_series, build_within_h_label
from recession_risk.features.transforms import aggregate_to_monthly, compute_sahm_gap, compute_term_spread, load_fred_csv
from recession_risk.ingest.nber import build_monthly_recession_series, load_chronology


@dataclass
class SeriesAvailability:
    values: pd.Series
    feature_date_used: pd.Timestamp | None
    vintage_date: pd.Timestamp | None


@dataclass
class SeriesCache:
    spec: dict
    raw_monthly: pd.Series
    raw_available_dates: pd.Series
    vintage_frame: pd.DataFrame | None


def build_realtime_monthly_panel(config: dict, aggregation: str | None = None) -> pd.DataFrame:
    aggregation_method = aggregation or config["aggregation"]["default"]
    raw_dir = config["paths"]["raw_data"]
    reference_dir = config["paths"]["reference_data"]

    raw_series = {
        series_id: load_fred_csv(raw_dir / f"{series_id}.csv", series_id)
        for series_id in config["series"]
    }
    series_caches = {
        series_id: prepare_series_cache(series_id, raw_frame, config, aggregation_method)
        for series_id, raw_frame in raw_series.items()
    }
    forecast_dates = determine_forecast_dates(raw_series)
    chronology = load_chronology(reference_dir / "nber_chronology.csv")
    recession = build_monthly_recession_series(chronology, forecast_dates.min(), forecast_dates.max())

    rows: list[dict[str, object]] = []
    for forecast_date in forecast_dates:
        row = {"date": forecast_date, "forecast_date": forecast_date, "aggregation_method": aggregation_method}
        per_series: dict[str, SeriesAvailability] = {}
        for series_id in raw_series:
            per_series[series_id] = series_latest_available_value(
                series_id=series_id,
                as_of_date=forecast_date,
                config=config,
                cache=series_caches[series_id],
            )
            row[series_id] = scalar_from_history(per_series[series_id].values)
            row[f"{series_id}_feature_date_used"] = timestamp_to_string(per_series[series_id].feature_date_used)
            row[f"{series_id}_series_vintage_date"] = timestamp_to_string(per_series[series_id].vintage_date)

        row["term_spread"] = row["DGS10"] - row["DTB3"] if pd.notna(row["DGS10"]) and pd.notna(row["DTB3"]) else pd.NA
        row["sahm_gap"] = scalar_from_history(compute_sahm_gap(per_series["UNRATE"].values)) if not per_series["UNRATE"].values.empty else pd.NA
        rows.append(row)

    panel = pd.DataFrame(rows).set_index("date").sort_index()
    panel["current_recession"] = recession.reindex(panel.index, fill_value=0).astype("int64")
    panel["recession_start"] = build_recession_start_series(panel["current_recession"])
    for horizon in config["horizons"]:
        panel[f"within_{horizon}m"] = build_within_h_label(panel["current_recession"], horizon)
    return panel.reset_index()


def determine_forecast_dates(raw_series: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    monthly_starts = []
    for frame in raw_series.values():
        months = frame["date"].dt.to_period("M").dt.to_timestamp()
        monthly_starts.append(months)
    combined = pd.concat(monthly_starts, ignore_index=True)
    return pd.DatetimeIndex(sorted(combined.drop_duplicates()))


def series_latest_available_value(
    series_id: str,
    as_of_date: pd.Timestamp,
    config: dict,
    cache: SeriesCache,
) -> SeriesAvailability:
    monthly_history, vintage_dates = series_history_asof(series_id, as_of_date, config, cache)
    feature_date_used = monthly_history.index.max() if not monthly_history.empty else None
    vintage_date = None if feature_date_used is None else vintage_dates.get(feature_date_used)
    return SeriesAvailability(monthly_history, feature_date_used, vintage_date)


def prepare_series_cache(series_id: str, raw_frame: pd.DataFrame, config: dict, aggregation: str) -> SeriesCache:
    spec = get_series_spec(config, series_id)
    if spec.get("frequency") == "daily":
        raw_monthly = aggregate_to_monthly(raw_frame, series_id, aggregation)
    else:
        monthly = raw_frame.copy()
        monthly["date"] = monthly["date"].dt.to_period("M").dt.to_timestamp()
        raw_monthly = monthly.drop_duplicates(subset=["date"], keep="last").set_index("date")[series_id].sort_index()

    raw_available_dates = raw_monthly.index.to_series().apply(lambda idx: get_available_date(spec, idx))
    use_vintages = bool(config.get("realtime", {}).get("use_vintages")) and spec.get("vintage_source")
    vintage_frame = None
    if use_vintages:
        vintage_path = config["paths"]["vintage_data"] / f"{series_id}.csv"
        if vintage_path.exists():
            vintage_frame = load_vintage_frame(vintage_path, series_id)
    return SeriesCache(spec=spec, raw_monthly=raw_monthly, raw_available_dates=raw_available_dates, vintage_frame=vintage_frame)


def series_history_asof(
    series_id: str,
    as_of_date: pd.Timestamp,
    config: dict,
    cache: SeriesCache,
) -> tuple[pd.Series, dict[pd.Timestamp, pd.Timestamp | None]]:
    spec = cache.spec
    use_vintages = bool(config.get("realtime", {}).get("use_vintages")) and spec.get("vintage_source")
    vintage_frame = get_series_asof(series_id, as_of_date, config, vintage_frame=cache.vintage_frame) if use_vintages else pd.DataFrame(columns=["date", series_id, "vintage_date"])

    if not vintage_frame.empty:
        vintage_lookup = {
            pd.Timestamp(row.date).to_period("M").to_timestamp(): pd.Timestamp(row.vintage_date)
            for row in vintage_frame.itertuples(index=False)
        }
        if spec.get("frequency") == "daily":
            monthly = aggregate_to_monthly(vintage_frame.loc[:, ["date", series_id]].copy(), series_id, spec.get("aggregation", "mean"))
        else:
            monthly = vintage_frame.copy()
            monthly["date"] = monthly["date"].dt.to_period("M").dt.to_timestamp()
            monthly = monthly.drop_duplicates(subset=["date"], keep="last").set_index("date")[series_id].sort_index()
        available_dates = monthly.index.to_series().apply(lambda idx: get_available_date(spec, idx))
        available = monthly[available_dates <= as_of_date.normalize()].copy()
        vintage_dates = {timestamp: vintage_lookup.get(timestamp) for timestamp in available.index}
        return available, vintage_dates

    available = cache.raw_monthly[cache.raw_available_dates <= as_of_date.normalize()].copy()
    vintage_dates = {timestamp: None for timestamp in available.index}
    return available, vintage_dates


def scalar_from_history(history: pd.Series) -> float | pd.NA:
    if history.empty:
        return pd.NA
    return float(history.iloc[-1])


def timestamp_to_string(value: pd.Timestamp | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()
