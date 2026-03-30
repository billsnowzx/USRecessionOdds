from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from helpers import write_reference_data, write_synthetic_raw_data, write_test_config, write_unrate_vintages

from recession_risk.config import load_config
from recession_risk.ingest.fred import ingest_all_series
from recession_risk.pipeline import build_monthly_panel, save_monthly_panel


def test_registry_drives_panel_without_series_block():
    base_dir = make_workspace()
    try:
        write_synthetic_raw_data(base_dir / "data" / "raw")
        write_reference_data(base_dir / "data" / "reference")
        config = load_config(write_test_config(base_dir))
        config.pop("series", None)

        panel = build_monthly_panel(config)

        assert {
            "DGS10",
            "DTB3",
            "UNRATE",
            "BAMLH0A0HYM2",
            "PAYEMS_growth_3m_ann",
            "AMTMNO_change_3m",
            "US_OECD_CLI_growth_3m",
            "equity_drawdown_6m",
            "term_spread",
            "sahm_gap",
        }.issubset(panel.columns)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def test_ingest_and_panel_write_metadata_sidecars_without_network():
    base_dir = make_workspace()
    try:
        write_synthetic_raw_data(base_dir / "data" / "raw")
        write_reference_data(base_dir / "data" / "reference")
        write_unrate_vintages(base_dir / "data" / "vintages")
        config = load_config(write_test_config(base_dir))

        ingest_all_series(config, refresh=False, include_vintages=True)
        panel = build_monthly_panel(config)
        csv_path, _ = save_monthly_panel(panel, config)

        raw_metadata = json.loads((base_dir / "data" / "raw" / "DGS10.metadata.json").read_text(encoding="utf-8"))
        panel_metadata = json.loads(csv_path.with_suffix(".metadata.json").read_text(encoding="utf-8"))

        assert raw_metadata["series_id"] == "DGS10"
        assert raw_metadata["checksum_sha256"]
        assert raw_metadata["pull_timestamp_utc"]
        assert panel_metadata["data_mode"] == "latest_available"
        assert panel_metadata["series_registry_path"].endswith("series_registry.yaml")
        assert len(panel_metadata["series"]) == 8
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def make_workspace() -> Path:
    base_dir = Path("D:/AI/Recession_Odds/test_runs") / uuid4().hex
    base_dir.mkdir(parents=True, exist_ok=False)
    return base_dir
