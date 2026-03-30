from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
from helpers import write_reference_data, write_synthetic_raw_data, write_test_config, write_unrate_vintages

from recession_risk.backtest.realtime_runner import run_realtime_backtest, save_realtime_outputs
from recession_risk.config import load_config
from recession_risk.data.release_calendar import get_available_date
from recession_risk.pipeline import build_monthly_panel, save_monthly_panel


def test_release_calendar_respects_monthly_lag():
    spec = {"frequency": "monthly", "release_lag_months": 1, "release_lag_days": 5}
    assert get_available_date(spec, "2000-01-01") == pd.Timestamp("2000-03-05")


def test_realtime_panel_uses_vintage_and_release_lag():
    base_dir = make_workspace()
    try:
        write_synthetic_raw_data(base_dir / "data" / "raw")
        write_reference_data(base_dir / "data" / "reference")
        write_unrate_vintages(base_dir / "data" / "vintages")
        config = load_config(write_test_config(base_dir))

        latest_panel = build_monthly_panel(config, data_mode="latest_available")
        realtime_panel = build_monthly_panel(config, data_mode="realtime")

        latest_row = latest_panel.loc[latest_panel["date"] == pd.Timestamp("2000-02-01")].iloc[0]
        realtime_row = realtime_panel.loc[realtime_panel["date"] == pd.Timestamp("2000-02-01")].iloc[0]

        assert latest_row["UNRATE"] != realtime_row["UNRATE"]
        assert realtime_row["UNRATE_feature_date_used"] == "1999-11-01"
        assert realtime_row["UNRATE_series_vintage_date"] == "1999-12-06"
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def test_realtime_backtest_generates_archived_predictions():
    base_dir = make_workspace()
    try:
        write_synthetic_raw_data(base_dir / "data" / "raw")
        write_reference_data(base_dir / "data" / "reference")
        write_unrate_vintages(base_dir / "data" / "vintages")
        config = load_config(write_test_config(base_dir))

        realtime_panel = build_monthly_panel(config, data_mode="realtime")
        save_monthly_panel(realtime_panel, config, data_mode="realtime")
        predictions, metrics = run_realtime_backtest(config)
        predictions_path, metrics_path = save_realtime_outputs(predictions, metrics, config)

        assert predictions_path.exists()
        assert metrics_path.exists()
        assert {"forecast_date", "model_name", "score", "signal"}.issubset(predictions.columns)
        assert set(metrics["model_name"]) == {
            "yield_curve_logit_realtime",
            "yield_curve_inversion_realtime",
            "hy_credit_logit_realtime",
            "sahm_rule_realtime",
        }
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def make_workspace() -> Path:
    base_dir = Path("D:/AI/Recession_Odds/test_runs") / uuid4().hex
    base_dir.mkdir(parents=True, exist_ok=False)
    return base_dir
