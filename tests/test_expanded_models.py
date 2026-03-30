from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from helpers import write_reference_data, write_synthetic_raw_data, write_test_config, write_unrate_vintages

from recession_risk.backtest.expanded_runner import run_expanded_models, save_expanded_outputs
from recession_risk.cli import main
from recession_risk.config import load_config
from recession_risk.pipeline import build_monthly_panel, save_monthly_panel


def test_expanded_models_run_and_emit_summaries():
    base_dir = make_workspace()
    try:
        write_synthetic_raw_data(base_dir / "data" / "raw")
        write_reference_data(base_dir / "data" / "reference")
        write_unrate_vintages(base_dir / "data" / "vintages")
        config = load_config(write_test_config(base_dir))

        panel = build_monthly_panel(config)
        save_monthly_panel(panel, config)
        predictions, metrics, summaries = run_expanded_models(panel, config, data_mode="latest_available")
        predictions_path, metrics_path, summaries_path = save_expanded_outputs(predictions, metrics, summaries, config, "latest_available")
        backtests_dir = config["paths"]["outputs"] / "backtests"

        assert predictions_path.exists()
        assert metrics_path.exists()
        assert summaries_path.exists()
        assert (backtests_dir / "expanded_event_scorecard.csv").exists()
        assert (backtests_dir / "expanded_episode_summary.csv").exists()
        assert (backtests_dir / "expanded_threshold_analysis.csv").exists()
        assert not predictions.empty
        assert set(predictions["model_name"]).issuperset(
            {
                "multivariate_logit_within_12m",
                "regularized_logit_within_12m",
                "multivariate_logit_current_recession",
                "regularized_logit_current_recession",
            }
        )
        assert {"feature", "coefficient", "model_name", "target_name"}.issubset(summaries.columns)

    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def test_cli_run_expanded_models_latest_and_realtime():
    base_dir = make_workspace()
    try:
        write_synthetic_raw_data(base_dir / "data" / "raw")
        write_reference_data(base_dir / "data" / "reference")
        write_unrate_vintages(base_dir / "data" / "vintages")
        config_path = write_test_config(base_dir)

        assert main(["--config", str(config_path), "build-panel"]) == 0
        assert main(["--config", str(config_path), "run-expanded-models"]) == 0
        assert main(["--config", str(config_path), "build-panel", "--data-mode", "realtime"]) == 0
        assert main(["--config", str(config_path), "run-expanded-models", "--data-mode", "realtime"]) == 0
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def make_workspace() -> Path:
    base_dir = Path("D:/AI/Recession_Odds/test_runs") / uuid4().hex
    base_dir.mkdir(parents=True, exist_ok=False)
    return base_dir
