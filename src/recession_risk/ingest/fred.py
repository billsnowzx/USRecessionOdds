from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen


FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def download_fred_series(series_id: str, output_path: str | Path, timeout: int = 30) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = FRED_CSV_URL.format(series_id=series_id)
    with urlopen(url, timeout=timeout) as response:
        destination.write_bytes(response.read())
    return destination


def ingest_all_series(config: dict, refresh: bool = False) -> list[Path]:
    raw_dir = config["paths"]["raw_data"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for series_id in config["series"]:
        path = raw_dir / f"{series_id}.csv"
        if refresh or not path.exists():
            download_fred_series(series_id, path)
        outputs.append(path)
    return outputs
