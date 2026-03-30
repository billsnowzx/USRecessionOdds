from __future__ import annotations

import argparse

import pandas as pd

from recession_risk.backtest.runner import (
    run_baseline_backtests,
    run_robustness_backtests,
    save_baseline_outputs,
)
from recession_risk.config import load_config
from recession_risk.ingest.fred import ingest_all_series
from recession_risk.pipeline import build_monthly_panel, load_monthly_panel, save_monthly_panel
from recession_risk.reporting.report import render_html_summary, render_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recession risk replication pipeline")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Download raw FRED files")
    ingest_parser.add_argument("--refresh", action="store_true", help="Re-download existing raw files")

    panel_parser = subparsers.add_parser("build-panel", help="Build processed monthly panel")
    panel_parser.add_argument("--aggregation", choices=["mean", "eom"], help="Override aggregation method")

    subparsers.add_parser("run-baselines", help="Run baseline backtests")
    subparsers.add_parser("run-robustness", help="Run robustness experiments")
    subparsers.add_parser("render-report", help="Render the Markdown report")
    subparsers.add_parser("render-html-summary", help="Render the HTML time-series summary")

    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "ingest":
        for path in ingest_all_series(config, refresh=args.refresh):
            print(path)
        return 0

    if args.command == "build-panel":
        panel = build_monthly_panel(config, aggregation=args.aggregation)
        for path in save_monthly_panel(panel, config):
            print(path)
        return 0

    if args.command == "run-baselines":
        panel = ensure_panel(config)
        predictions, metrics = run_baseline_backtests(panel, config)
        for path in save_baseline_outputs(predictions, metrics, config):
            print(path)
        return 0

    if args.command == "run-robustness":
        robustness = run_robustness_backtests(config)
        print(config["paths"]["reports"] / "tables" / "robustness_metrics.csv")
        print(f"{len(robustness)} rows")
        return 0

    if args.command == "render-report":
        panel = ensure_panel(config)
        predictions = pd.read_csv(
            config["paths"]["reports"] / "tables" / "baseline_predictions.csv",
            parse_dates=["date", "train_end", "test_start"],
        )
        metrics = pd.read_csv(config["paths"]["reports"] / "tables" / "baseline_metrics.csv")
        print(render_report(panel, predictions, metrics, config))
        return 0

    if args.command == "render-html-summary":
        panel = ensure_panel(config)
        predictions = pd.read_csv(
            config["paths"]["reports"] / "tables" / "baseline_predictions.csv",
            parse_dates=["date", "train_end", "test_start"],
        )
        metrics = pd.read_csv(config["paths"]["reports"] / "tables" / "baseline_metrics.csv")
        print(render_html_summary(panel, predictions, metrics, config))
        return 0

    return 1


def ensure_panel(config: dict) -> pd.DataFrame:
    panel_path = config["paths"]["processed_data"] / "monthly_panel.csv"
    if panel_path.exists():
        return load_monthly_panel(config)
    panel = build_monthly_panel(config)
    save_monthly_panel(panel, config)
    return panel


if __name__ == "__main__":
    raise SystemExit(main())