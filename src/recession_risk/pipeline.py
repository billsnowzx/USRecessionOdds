from __future__ import annotations

from pathlib import Path

import pandas as pd

from recession_risk.data.cache_metadata import file_sha256, utc_now_iso, write_metadata
from recession_risk.data.registry import list_series_ids, list_series_specs
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
    series_specs = list_series_specs(config)

    monthly_series: dict[str, pd.Series] = {}
    for series_id in list_series_ids(config):
        frame = load_fred_csv(raw_dir / f"{series_id}.csv", series_id)
        series_spec = series_specs[series_id]
        if series_spec.get("frequency") == "daily":
            monthly_series[series_id] = aggregate_to_monthly(
                frame,
                series_id,
                series_spec.get("aggregation", aggregation_method),
            )
        else:
            monthly = frame.copy()
            monthly["date"] = monthly["date"].dt.to_period("M").dt.to_timestamp()
            monthly_series[series_id] = (
                monthly.drop_duplicates(subset=["date"], keep="last")
                .set_index("date")[series_id]
                .sort_index()
            )

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
    selected_mode = data_mode or config.get("data_mode", "latest_available")
    suffix = "" if selected_mode == "latest_available" else "_realtime"
    csv_path = processed_dir / f"monthly_panel{suffix}.csv"
    parquet_path = processed_dir / f"monthly_panel{suffix}.parquet"
    panel.to_csv(csv_path, index=False)
    panel.to_parquet(parquet_path, index=False)
    write_panel_metadata(panel, config, csv_path, parquet_path, selected_mode)
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


def write_panel_metadata(
    panel: pd.DataFrame,
    config: dict,
    csv_path: Path,
    parquet_path: Path,
    data_mode: str,
) -> None:
    raw_metadata = []
    for series_id, spec in list_series_specs(config).items():
        raw_path = config["paths"]["raw_data"] / f"{series_id}.csv"
        raw_entry = {
            "series_id": series_id,
            "source": spec.get("source"),
            "frequency": spec.get("frequency"),
            "aggregation": spec.get("aggregation"),
            "transform": spec.get("transform"),
            "realtime_eligible": bool(spec.get("realtime_eligible", False)),
            "raw_file": str(raw_path),
            "raw_checksum_sha256": file_sha256(raw_path) if raw_path.exists() else "",
        }
        vintage_path = config["paths"].get("vintage_data")
        if vintage_path:
            specific_vintage = vintage_path / f"{series_id}.csv"
            raw_entry["vintage_file"] = str(specific_vintage) if specific_vintage.exists() else ""
            raw_entry["vintage_checksum_sha256"] = file_sha256(specific_vintage) if specific_vintage.exists() else ""
        raw_metadata.append(raw_entry)

    write_metadata(
        csv_path,
        {
            "panel_generated_at_utc": utc_now_iso(),
            "data_mode": data_mode,
            "aggregation_method": str(panel.get("aggregation_method", pd.Series(dtype=object)).iloc[0]) if "aggregation_method" in panel.columns and not panel.empty else config["aggregation"]["default"],
            "row_count": int(len(panel)),
            "columns": list(panel.columns),
            "date_min": str(pd.Timestamp(panel["date"].min()).date()) if "date" in panel.columns and not panel.empty else "",
            "date_max": str(pd.Timestamp(panel["date"].max()).date()) if "date" in panel.columns and not panel.empty else "",
            "csv_file": str(csv_path),
            "csv_checksum_sha256": file_sha256(csv_path),
            "parquet_file": str(parquet_path),
            "parquet_checksum_sha256": file_sha256(parquet_path),
            "series_registry_path": str(config["series_registry_path"]),
            "series": raw_metadata,
        },
    )
