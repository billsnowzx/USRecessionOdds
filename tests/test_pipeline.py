from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from helpers import write_reference_data, write_synthetic_raw_data, write_test_config

from recession_risk.backtest.runner import run_baseline_backtests, run_robustness_backtests, save_baseline_outputs
from recession_risk.cli import main
from recession_risk.config import load_config
from recession_risk.pipeline import build_monthly_panel, save_monthly_panel
from recession_risk.reporting.report import render_report


def test_pipeline_runs_end_to_end_with_offline_fixture():
    base_dir = make_workspace()
    try:
        raw_dir = base_dir / "data" / "raw"
        reference_dir = base_dir / "data" / "reference"
        write_synthetic_raw_data(raw_dir)
        write_reference_data(reference_dir)
        config_path = write_test_config(base_dir)
        config = load_config(config_path)

        panel = build_monthly_panel(config)
        save_monthly_panel(panel, config)
        predictions, metrics = run_baseline_backtests(panel, config)
        prediction_path, metrics_path = save_baseline_outputs(predictions, metrics, config)
        report_path = render_report(panel, predictions, metrics, config)
        robustness = run_robustness_backtests(config)
        backtests_dir = config["paths"]["outputs"] / "backtests"

        assert prediction_path.exists()
        assert metrics_path.exists()
        assert report_path.exists()
        assert not robustness.empty
        assert (backtests_dir / "baseline_event_scorecard.csv").exists()
        assert (backtests_dir / "baseline_episode_summary.csv").exists()
        assert (backtests_dir / "baseline_threshold_analysis.csv").exists()
        assert set(metrics["model_name"]) == {
            "yield_curve_logit",
            "yield_curve_inversion",
            "hy_credit_logit",
            "sahm_rule",
        }
        assert {
            "auc",
            "precision",
            "recall",
            "event_hit_rate",
            "median_timing_months",
            "average_timing_months",
            "episode_recall",
            "max_false_alarm_streak",
        }.issubset(metrics.columns)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def test_cli_commands_run_with_fixture_data():
    base_dir = make_workspace()
    try:
        raw_dir = base_dir / "data" / "raw"
        reference_dir = base_dir / "data" / "reference"
        write_synthetic_raw_data(raw_dir)
        write_reference_data(reference_dir)
        config_path = write_test_config(base_dir)

        assert main(["--config", str(config_path), "build-panel"]) == 0
        assert main(["--config", str(config_path), "run-baselines"]) == 0
        assert main(["--config", str(config_path), "render-report"]) == 0
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def make_workspace() -> Path:
    base_dir = Path("D:/AI/Recession_Odds/test_runs") / uuid4().hex
    base_dir.mkdir(parents=True, exist_ok=False)
    return base_dir
