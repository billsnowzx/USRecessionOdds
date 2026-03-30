from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

from recession_risk.data.registry import get_series_spec
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
    for series_id in config["series"]:
        path = raw_dir / f"{series_id}.csv"
        if refresh or not path.exists():
            download_fred_series(series_id, path)
        outputs.append(path)
        if include_vintages:
            spec = get_series_spec(config, series_id)
            if spec.get("vintage_source"):
                vintage_dir = config["paths"]["vintage_data"]
                vintage_dir.mkdir(parents=True, exist_ok=True)
                vintage_path = vintage_dir / f"{series_id}.csv"
                if refresh or not vintage_path.exists():
                    download_alfred_series(series_id, vintage_path)
                outputs.append(vintage_path)
    return outputs
