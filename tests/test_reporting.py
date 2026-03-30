from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
from helpers import write_reference_data, write_synthetic_raw_data, write_test_config

from recession_risk.backtest.expanded_runner import run_expanded_models, save_expanded_outputs
from recession_risk.backtest.runner import run_baseline_backtests, save_baseline_outputs
from recession_risk.config import load_config
from recession_risk.pipeline import build_monthly_panel, save_monthly_panel
from recession_risk.reporting.report import render_html_summary, render_report
from recession_risk.reporting.snapshot import build_snapshot_tables


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
        assert (outputs_root / "tables" / "current_snapshot_latest_available.csv").exists()
        assert (outputs_root / "tables" / "current_snapshot_realtime.csv").exists()
        assert (outputs_root / "tables" / "model_comparison.csv").exists()
        assert (outputs_root / "tables" / "snapshot_mode_comparison.csv").exists()
        assert (outputs_root / "tables" / "model_selection_quality.csv").exists()
        assert (outputs_root / "current_snapshot" / "current_snapshot.md").exists()
        assert (outputs_root / "historical_comparison" / "historical_comparison.md").exists()
        assert (outputs_root / "charts" / "selected_probabilities_latest_available.png").exists()
        assert (outputs_root / "charts" / "historical_percentiles_latest_available.png").exists()
        assert "Current Snapshot" in report_path.read_text(encoding="utf-8")
        assert "U.S. Recession Odds Monitor" in html_path.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def test_snapshot_selection_falls_back_to_benchmark_when_expanded_model_fails_gates():
    base_dir = make_workspace()
    try:
        config = load_config(write_test_config(base_dir))
        predictions = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
                "forecast_date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
                "target_name": ["within_12m", "within_12m"],
                "horizon": [12, 12],
                "model_name": ["yield_curve_logit", "multivariate_logit_within_12m"],
                "raw_score": [0.2, 0.8],
                "calibrated_score": [0.2, 0.8],
                "score": [0.2, 0.8],
                "signal": [False, True],
                "split_name": ["fixed", "expanded_holdout"],
                "train_end": ["1989-12-01", "1989-12-01"],
                "test_start": ["1990-01-01", "1990-01-01"],
                "actual": [0, 0],
                "feature_value": ["", ""],
                "features": ["term_spread", "term_spread,UNRATE"],
            }
        )
        metrics = pd.DataFrame(
            {
                "model_name": ["yield_curve_logit", "multivariate_logit_within_12m"],
                "target_name": ["within_12m", "within_12m"],
                "horizon": [12, 12],
                "split_name": ["fixed", "expanded_holdout"],
                "test_start": ["1990-01-01", "1990-01-01"],
                "auc": [0.80, 0.55],
                "precision": [0.3, 0.2],
                "recall": [0.3, 0.2],
                "f1": [0.3, 0.2],
                "false_positive_months": [10, 20],
                "brier_score": [0.1, 0.2],
                "ece": [0.05, 0.30],
                "event_hit_rate": [0.75, 0.25],
                "median_timing_months": [9.0, 4.0],
                "average_timing_months": [9.0, 4.0],
                "flagged_3m_ahead_share": [0.75, 0.25],
                "flagged_6m_ahead_share": [0.75, 0.25],
                "episode_recall": [0.75, 0.25],
                "max_false_alarm_streak": [12, 50],
                "event_hits": [3, 1],
                "n_events": [4, 4],
            }
        )

        snapshot, _, quality = build_snapshot_tables(predictions, metrics, config, "latest_available")

        assert snapshot.iloc[0]["Selected model"] == "Yield Curve Logit"
        assert "falling back to benchmark" in snapshot.iloc[0]["Selection note"].lower()
        assert bool(quality.loc[quality["Model"] == "Yield Curve Logit", "Selected"].iloc[0])
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def make_workspace() -> Path:
    base_dir = Path("D:/AI/Recession_Odds/test_runs") / uuid4().hex
    base_dir.mkdir(parents=True, exist_ok=False)
    return base_dir
