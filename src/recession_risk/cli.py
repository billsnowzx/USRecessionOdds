from __future__ import annotations

import argparse

import pandas as pd

from recession_risk.backtest.expanded_runner import run_expanded_models, save_expanded_outputs
from recession_risk.backtest.realtime_runner import run_realtime_backtest, save_realtime_outputs
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
    parser = argparse.ArgumentParser(description="U.S. recession odds platform")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Download raw FRED files")
    ingest_parser.add_argument("--refresh", action="store_true", help="Re-download existing raw files")
    ingest_parser.add_argument("--include-vintages", action="store_true", help="Also download configured ALFRED vintage files")

    panel_parser = subparsers.add_parser("build-panel", help="Build processed monthly panel")
    panel_parser.add_argument("--aggregation", choices=["mean", "eom"], help="Override aggregation method")
    panel_parser.add_argument("--data-mode", choices=["latest_available", "realtime"], help="Override configured data mode")

    subparsers.add_parser("run-baselines", help="Run baseline backtests")
    subparsers.add_parser("run-robustness", help="Run robustness experiments")
    subparsers.add_parser("run-realtime-backtest", help="Run pseudo-real-time expanding-window backtests")
    expanded_parser = subparsers.add_parser("run-expanded-models", help="Run multivariate and regularized logit models")
    expanded_parser.add_argument("--data-mode", choices=["latest_available", "realtime"], help="Override configured data mode")
    subparsers.add_parser("render-report", help="Render the Markdown report")
    subparsers.add_parser("render-html-summary", help="Render the HTML time-series summary")

    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "ingest":
        for path in ingest_all_series(config, refresh=args.refresh, include_vintages=args.include_vintages):
            print(path)
        return 0

    if args.command == "build-panel":
        panel = build_monthly_panel(config, aggregation=args.aggregation, data_mode=args.data_mode)
        for path in save_monthly_panel(panel, config, data_mode=args.data_mode):
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

    if args.command == "run-realtime-backtest":
        predictions, metrics = run_realtime_backtest(config)
        for path in save_realtime_outputs(predictions, metrics, config):
            print(path)
        return 0

    if args.command == "run-expanded-models":
        selected_mode = args.data_mode or config.get("data_mode", "latest_available")
        panel = ensure_panel(config, data_mode=selected_mode)
        predictions, metrics, summaries = run_expanded_models(panel, config, data_mode=selected_mode)
        for path in save_expanded_outputs(predictions, metrics, summaries, config, data_mode=selected_mode):
            print(path)
        return 0

    if args.command == "render-report":
        panel = ensure_panel(config, data_mode="latest_available")
        predictions = pd.read_csv(
            config["paths"]["reports"] / "tables" / "baseline_predictions.csv",
            parse_dates=["date", "train_end", "test_start"],
        )
        metrics = pd.read_csv(config["paths"]["reports"] / "tables" / "baseline_metrics.csv")
        print(render_report(panel, predictions, metrics, config))
        return 0

    if args.command == "render-html-summary":
        panel = ensure_panel(config, data_mode="latest_available")
        predictions = pd.read_csv(
            config["paths"]["reports"] / "tables" / "baseline_predictions.csv",
            parse_dates=["date", "train_end", "test_start"],
        )
        metrics = pd.read_csv(config["paths"]["reports"] / "tables" / "baseline_metrics.csv")
        print(render_html_summary(panel, predictions, metrics, config))
        return 0

    return 1


def ensure_panel(config: dict, data_mode: str | None = None) -> pd.DataFrame:
    suffix = "" if (data_mode or config.get("data_mode", "latest_available")) == "latest_available" else "_realtime"
    panel_path = config["paths"]["processed_data"] / f"monthly_panel{suffix}.csv"
    if panel_path.exists():
        return load_monthly_panel(config, data_mode=data_mode)
    panel = build_monthly_panel(config, data_mode=data_mode)
    save_monthly_panel(panel, config, data_mode=data_mode)
    return panel


if __name__ == "__main__":
    raise SystemExit(main())
