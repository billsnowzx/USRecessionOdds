from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from helpers import write_reference_data, write_synthetic_raw_data, write_test_config

from recession_risk.backtest.expanded_runner import run_expanded_models, save_expanded_outputs
from recession_risk.backtest.runner import run_baseline_backtests, save_baseline_outputs
from recession_risk.config import load_config
from recession_risk.pipeline import build_monthly_panel, save_monthly_panel
from recession_risk.reporting.report import render_html_summary, render_report


def test_reporting_writes_current_snapshot_and_historical_outputs():
    base_dir = make_workspace()
    try:
        write_synthetic_raw_data(base_dir / "data" / "raw")
        write_reference_data(base_dir / "data" / "reference")
        config = load_config(write_test_config(base_dir))

        panel = build_monthly_panel(config)
        save_monthly_panel(panel, config)
        baseline_predictions, baseline_metrics = run_baseline_backtests(panel, config)
        save_baseline_outputs(baseline_predictions, baseline_metrics, config)
        expanded_predictions, expanded_metrics, expanded_summaries = run_expanded_models(panel, config, data_mode="latest_available")
        save_expanded_outputs(expanded_predictions, expanded_metrics, expanded_summaries, config, "latest_available")

        report_path = render_report(panel, baseline_predictions, baseline_metrics, config)
        html_path = render_html_summary(panel, baseline_predictions, baseline_metrics, config)

        outputs_root = config["paths"]["outputs"] / "reports"
        assert report_path.exists()
        assert html_path.exists()
        assert (outputs_root / "tables" / "current_snapshot.csv").exists()
        assert (outputs_root / "tables" / "model_comparison.csv").exists()
        assert (outputs_root / "current_snapshot" / "current_snapshot.md").exists()
        assert (outputs_root / "historical_comparison" / "historical_comparison.md").exists()
        assert (outputs_root / "charts" / "selected_probabilities.png").exists()
        assert "Current Snapshot" in report_path.read_text(encoding="utf-8")
        assert "U.S. Recession Odds Monitor" in html_path.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def make_workspace() -> Path:
    base_dir = Path("D:/AI/Recession_Odds/test_runs") / uuid4().hex
    base_dir.mkdir(parents=True, exist_ok=False)
    return base_dir
