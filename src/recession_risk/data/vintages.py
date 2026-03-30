from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

import pandas as pd


ALFRED_CSV_URL = "https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={series_id}"


def download_alfred_series(series_id: str, output_path: str | Path, timeout: int = 30) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(ALFRED_CSV_URL.format(series_id=series_id), timeout=timeout) as response:
        destination.write_bytes(response.read())
    return destination


def load_vintage_frame(path: str | Path, series_id: str) -> pd.DataFrame:
    frame = pd.read_csv(path)

    if {"observation_date", "vintage_date", "value"}.issubset(frame.columns):
        normalized = frame.copy()
        normalized["observation_date"] = pd.to_datetime(normalized["observation_date"])
        normalized["vintage_date"] = pd.to_datetime(normalized["vintage_date"])
        normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
        return normalized.dropna(subset=["value"])

    if "observation_date" not in frame.columns:
        raise ValueError(f"Unexpected vintage file format for {series_id}: {path}")

    long_rows: list[dict[str, object]] = []
    for vintage_column in [column for column in frame.columns if column != "observation_date"]:
        vintage_ts = parse_vintage_column(vintage_column)
        values = pd.to_numeric(frame[vintage_column], errors="coerce")
        valid = frame.loc[values.notna(), ["observation_date"]].copy()
        valid["vintage_date"] = vintage_ts
        valid["value"] = values.loc[values.notna()].to_numpy()
        long_rows.extend(valid.to_dict(orient="records"))

    normalized = pd.DataFrame(long_rows)
    if normalized.empty:
        return pd.DataFrame(columns=["observation_date", "vintage_date", "value"])
    normalized["observation_date"] = pd.to_datetime(normalized["observation_date"])
    normalized["vintage_date"] = pd.to_datetime(normalized["vintage_date"])
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
    return normalized.dropna(subset=["value"]).sort_values(["observation_date", "vintage_date"]).reset_index(drop=True)


def get_series_asof(series_id: str, as_of_date: str | pd.Timestamp, config: dict, vintage_frame: pd.DataFrame | None = None) -> pd.DataFrame:
    as_of_ts = pd.Timestamp(as_of_date).normalize()
    if vintage_frame is None:
        vintage_cache = config.setdefault("_vintage_frames", {})
        if series_id not in vintage_cache:
            vintage_path = config["paths"]["vintage_data"] / f"{series_id}.csv"
            if not vintage_path.exists():
                vintage_cache[series_id] = pd.DataFrame(columns=["observation_date", "vintage_date", "value"])
            else:
                vintage_cache[series_id] = load_vintage_frame(vintage_path, series_id)
        vintage_frame = vintage_cache[series_id]
    if vintage_frame.empty:
        return pd.DataFrame(columns=["date", series_id, "vintage_date"])

    eligible = vintage_frame[vintage_frame["vintage_date"] <= as_of_ts].copy()
    if eligible.empty:
        return pd.DataFrame(columns=["date", series_id, "vintage_date"])

    latest = (
        eligible.sort_values(["observation_date", "vintage_date"])
        .groupby("observation_date", as_index=False)
        .tail(1)
        .rename(columns={"observation_date": "date", "value": series_id})
        .reset_index(drop=True)
    )
    return latest[["date", series_id, "vintage_date"]]


def parse_vintage_column(value: str) -> pd.Timestamp:
    try:
        return pd.Timestamp(value)
    except ValueError:
        suffix = value.rsplit("_", maxsplit=1)[-1]
        return pd.to_datetime(suffix, format="%Y%m%d")
