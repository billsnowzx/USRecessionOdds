from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

from recession_risk.data.cache_metadata import file_sha256, utc_now_iso, write_metadata
from recession_risk.data.registry import get_series_spec, list_series_ids
from recession_risk.data.vintages import download_alfred_series

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def download_fred_series(series_id: str, output_path: str | Path, timeout: int = 30) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = FRED_CSV_URL.format(series_id=series_id)
    with urlopen(url, timeout=timeout) as response:
        destination.write_bytes(response.read())
    return destination


def ingest_all_series(config: dict, refresh: bool = False, include_vintages: bool = False) -> list[Path]:
    raw_dir = config["paths"]["raw_data"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for series_id in list_series_ids(config):
        spec = get_series_spec(config, series_id)
        path = raw_dir / f"{series_id}.csv"
        if refresh or not path.exists():
            download_fred_series(series_id, path)
        outputs.append(path)
        write_series_metadata(path, series_id, spec, FRED_CSV_URL.format(series_id=series_id), source_kind="raw")
        if include_vintages:
            if spec.get("vintage_source"):
                vintage_dir = config["paths"]["vintage_data"]
                vintage_dir.mkdir(parents=True, exist_ok=True)
                vintage_path = vintage_dir / f"{series_id}.csv"
                if refresh or not vintage_path.exists():
                    download_alfred_series(series_id, vintage_path)
                outputs.append(vintage_path)
                write_series_metadata(
                    vintage_path,
                    series_id,
                    spec,
                    f"https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={series_id}",
                    source_kind="vintage",
                )
    return outputs


def write_series_metadata(path: Path, series_id: str, spec: dict, source_url: str, source_kind: str) -> None:
    write_metadata(
        path,
        {
            "series_id": series_id,
            "source_kind": source_kind,
            "source": spec.get("source", "FRED"),
            "source_url": source_url,
            "pull_timestamp_utc": utc_now_iso(),
            "frequency": spec.get("frequency"),
            "aggregation": spec.get("aggregation"),
            "transform": spec.get("transform"),
            "realtime_eligible": bool(spec.get("realtime_eligible", False)),
            "vintage_source": spec.get("vintage_source"),
            "checksum_sha256": file_sha256(path),
            "file_name": path.name,
        },
    )
