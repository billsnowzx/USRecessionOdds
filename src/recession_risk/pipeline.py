from __future__ import annotations

from pathlib import Path

import pandas as pd

from recession_risk.data.realtime_panel import build_realtime_monthly_panel
from recession_risk.features.labels import build_recession_start_series, build_within_h_label
from recession_risk.features.transforms import (
    aggregate_to_monthly,
    combine_monthly_series,
    compute_sahm_gap,
    compute_term_spread,
    load_fred_csv,
)
from recession_risk.ingest.nber import build_monthly_recession_series, load_chronology


def build_monthly_panel(
    config: dict,
    aggregation: str | None = None,
    data_mode: str | None = None,
) -> pd.DataFrame:
    selected_mode = data_mode or config.get("data_mode", "latest_available")
    if selected_mode == "realtime":
        return build_realtime_monthly_panel(config, aggregation=aggregation)

    aggregation_method = aggregation or config["aggregation"]["default"]
    raw_dir = config["paths"]["raw_data"]
    reference_dir = config["paths"]["reference_data"]

    monthly_series: dict[str, pd.Series] = {}
    for series_id in config["series"]:
        frame = load_fred_csv(raw_dir / f"{series_id}.csv", series_id)
        monthly_series[series_id] = aggregate_to_monthly(frame, series_id, aggregation_method)

    panel = combine_monthly_series(monthly_series)
    chronology = load_chronology(reference_dir / "nber_chronology.csv")
    recession = build_monthly_recession_series(chronology, panel["date"].min(), panel["date"].max())

    panel = panel.set_index("date").sort_index()
    panel["current_recession"] = recession.reindex(panel.index, fill_value=0).astype("int64")
    panel["term_spread"] = compute_term_spread(panel)
    panel["sahm_gap"] = compute_sahm_gap(panel["UNRATE"])
    panel["recession_start"] = build_recession_start_series(panel["current_recession"])

    for horizon in config["horizons"]:
        panel[f"within_{horizon}m"] = build_within_h_label(panel["current_recession"], horizon)

    panel["aggregation_method"] = aggregation_method
    return panel.reset_index()


def save_monthly_panel(panel: pd.DataFrame, config: dict, data_mode: str | None = None) -> tuple[Path, Path]:
    processed_dir = config["paths"]["processed_data"]
    processed_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if (data_mode or config.get("data_mode", "latest_available")) == "latest_available" else "_realtime"
    csv_path = processed_dir / f"monthly_panel{suffix}.csv"
    parquet_path = processed_dir / f"monthly_panel{suffix}.parquet"
    panel.to_csv(csv_path, index=False)
    panel.to_parquet(parquet_path, index=False)
    return csv_path, parquet_path


def load_monthly_panel(config: dict, data_mode: str | None = None) -> pd.DataFrame:
    suffix = "" if (data_mode or config.get("data_mode", "latest_available")) == "latest_available" else "_realtime"
    csv_path = config["paths"]["processed_data"] / f"monthly_panel{suffix}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Processed panel not found: {csv_path}")
    frame = pd.read_csv(csv_path)
    for date_column in [column for column in ["date", "forecast_date"] if column in frame.columns]:
        frame[date_column] = pd.to_datetime(frame[date_column])
    return frame
