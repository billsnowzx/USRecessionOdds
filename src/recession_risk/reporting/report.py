from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from recession_risk.backtest.plots import (
    plot_calibration,
    plot_probability_over_time,
    plot_roc_curves,
    plot_series_with_recessions,
)
from recession_risk.ingest.nber import extract_recession_periods
from recession_risk.pipeline import load_monthly_panel
from recession_risk.reporting.snapshot import (
    build_mode_comparison_table,
    build_portfolio_interpretation,
    build_signal_driver_summary,
    build_snapshot_tables,
    ensure_output_report_dirs,
    load_episode_summary,
    load_reporting_inputs,
    model_disagreement_text,
    model_title,
    render_reporting_charts,
    snapshot_overall_regime,
    write_reporting_tables,
    write_supporting_markdown,
)

MODEL_SPECS = {
    "yield_curve_logit": {
        "title": "Yield-Curve Logit",
        "kind": "score",
        "threshold": 0.5,
        "ylabel": "Probability",
        "color": "#c44e52",
    },
    "yield_curve_inversion": {
        "title": "Yield-Curve Inversion Rule",
        "kind": "signal",
        "threshold": 0.5,
        "ylabel": "Signal",
        "color": "#4c72b0",
    },
    "hy_credit_logit": {
        "title": "HY Credit Logit",
        "kind": "score",
        "threshold": 0.5,
        "ylabel": "Probability",
        "color": "#55a868",
    },
    "sahm_rule": {
        "title": "Sahm Rule",
        "kind": "score",
        "threshold": 0.5,
        "ylabel": "Gap",
        "color": "#8172b2",
    },
}


def render_report(panel: pd.DataFrame, predictions: pd.DataFrame, metrics: pd.DataFrame, config: dict) -> Path:
    reports_dir = config["paths"]["reports"]
    figures_dir = reports_dir / "figures"
    tables_dir = reports_dir / "tables"
    output_dirs = ensure_output_report_dirs(config)
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    recession_periods = extract_recession_periods(panel.set_index("date")["current_recession"].astype(int))
    modes = enabled_snapshot_modes(config)
    realtime_panel = load_optional_panel(config, "realtime") if "realtime" in modes else pd.DataFrame()

    latest_predictions, latest_metrics = load_reporting_inputs(config, predictions, metrics, data_mode="latest_available")
    realtime_predictions, realtime_metrics = (
        load_reporting_inputs(config, predictions, metrics, data_mode="realtime") if "realtime" in modes else (pd.DataFrame(), pd.DataFrame())
    )

    latest_snapshot, latest_comparison, latest_quality = build_snapshot_tables(latest_predictions, latest_metrics, config, "latest_available")
    realtime_snapshot, realtime_comparison, realtime_quality = build_snapshot_tables(realtime_predictions, realtime_metrics, config, "realtime")
    mode_comparison = build_mode_comparison_table(latest_snapshot, realtime_snapshot, config)
    quality = pd.concat([latest_quality, realtime_quality], ignore_index=True, sort=False) if not latest_quality.empty or not realtime_quality.empty else pd.DataFrame()
    episode_summary = load_episode_summary(config)
    chart_paths = render_reporting_charts(
        latest_snapshot,
        latest_comparison,
        latest_predictions,
        realtime_snapshot,
        realtime_comparison,
        realtime_predictions,
        episode_summary,
        recession_periods,
        output_dirs,
    )
    write_reporting_tables(
        latest_snapshot,
        latest_comparison,
        realtime_snapshot,
        realtime_comparison,
        mode_comparison,
        quality,
        output_dirs,
    )
    write_supporting_markdown(
        latest_snapshot,
        latest_comparison,
        realtime_snapshot,
        realtime_comparison,
        mode_comparison,
        quality,
        chart_paths,
        output_dirs,
    )

    plot_series_with_recessions(
        panel.set_index("date")["term_spread"].dropna(),
        recession_periods,
        figures_dir / "term_spread.png",
        title="10Y minus 3M term spread",
        ylabel="Percentage points",
    )
    yield_probs = predictions[predictions["model_name"] == "yield_curve_logit"].copy()
    if not yield_probs.empty:
        plot_probability_over_time(
            yield_probs,
            recession_periods,
            figures_dir / "yield_curve_probability.png",
            title="Yield-curve probability of recession within 12 months",
        )
        plot_calibration(
            yield_probs,
            figures_dir / "yield_curve_calibration.png",
            title="Yield-curve calibration",
        )
    plot_roc_curves(predictions, figures_dir / "baseline_roc.png")

    latest_signal_summary = build_signal_driver_summary(panel, latest_snapshot, latest_comparison, mode_comparison)
    realtime_signal_summary = build_signal_driver_summary(realtime_panel, realtime_snapshot, realtime_comparison, mode_comparison) if not realtime_panel.empty else "Realtime signal summary unavailable."

    report = "\n".join(
        [
            "# Recession Risk Monitoring Report",
            "",
            "## Current Snapshot",
            "",
            "### Latest Available",
            "",
            latest_snapshot.drop(columns=["model_name"], errors="ignore").round(4).to_markdown(index=False) if not latest_snapshot.empty else "No latest-available snapshot data available.",
            "",
            f"Overall regime: {snapshot_overall_regime(latest_snapshot)}",
            "",
            "### Realtime",
            "",
            realtime_snapshot.drop(columns=["model_name"], errors="ignore").round(4).to_markdown(index=False) if not realtime_snapshot.empty else "No realtime snapshot data available.",
            "",
            f"Overall realtime regime: {snapshot_overall_regime(realtime_snapshot)}",
            "",
            "### Latest vs Realtime",
            "",
            mode_comparison.round(4).to_markdown(index=False) if not mode_comparison.empty else "No mode comparison available.",
            "",
            "## Snapshot Governance",
            "",
            quality.round(4).to_markdown(index=False) if not quality.empty else "No model quality table available.",
            "",
            "## Signal Drivers",
            "",
            "### Latest Available",
            "",
            latest_signal_summary,
            "",
            "### Realtime",
            "",
            realtime_signal_summary,
            "",
            "## Current Model Comparison",
            "",
            "### Latest Available",
            "",
            latest_comparison.round(4).to_markdown(index=False) if not latest_comparison.empty else "No latest-available comparison data available.",
            "",
            "### Realtime",
            "",
            realtime_comparison.round(4).to_markdown(index=False) if not realtime_comparison.empty else "No realtime comparison data available.",
            "",
            "## Historical Comparison",
            "",
            f"![Latest available selected probabilities](../outputs/reports/charts/{chart_paths['selected_probabilities_latest_available'].name})",
            "",
            f"![Realtime selected probabilities](../outputs/reports/charts/{chart_paths['selected_probabilities_realtime'].name})",
            "",
            f"![Latest available percentiles](../outputs/reports/charts/{chart_paths['historical_percentiles_latest_available'].name})",
            "",
            f"![Realtime percentiles](../outputs/reports/charts/{chart_paths['historical_percentiles_realtime'].name})",
            "",
            f"![Latest available model comparison](../outputs/reports/charts/{chart_paths['current_model_comparison_latest_available'].name})",
            "",
            f"![Realtime model comparison](../outputs/reports/charts/{chart_paths['current_model_comparison_realtime'].name})",
            "",
            f"![Episode warning timing](../outputs/reports/charts/{chart_paths['episode_warning_timing'].name})",
            "",
            "## Baseline Metrics",
            "",
            metrics.round(4).to_markdown(index=False),
            "",
            "## Baseline Figures",
            "",
            "![Term spread](figures/term_spread.png)",
            "",
            "![Yield curve probability](figures/yield_curve_probability.png)",
            "",
            "![ROC curves](figures/baseline_roc.png)",
            "",
            "![Yield curve calibration](figures/yield_curve_calibration.png)",
            "",
            "## Portfolio Interpretation",
            "",
            build_portfolio_interpretation(latest_snapshot, config) if config.get("reporting", {}).get("include_portfolio_interpretation", True) else "Portfolio interpretation disabled in config.",
            "",
            "## Notes",
            "",
            "- Benchmarks remain the permanent reference layer and are retained even when expanded models are available.",
            "- Expanded-model snapshots are quality-gated; if no expanded candidate passes, the report falls back to the best benchmark for that target.",
            "- Latest-available and realtime views are reported separately to avoid presenting hindsight and as-of probabilities as the same object.",
            "- Rule models remain uncalibrated signals; probability-scored expanded models use calibrated probabilities in investor-facing outputs.",
        ]
    )
    report_path = reports_dir / "recession_risk_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def render_html_summary(panel: pd.DataFrame, predictions: pd.DataFrame, metrics: pd.DataFrame, config: dict) -> Path:
    reports_dir = config["paths"]["reports"]
    assets_dir = reports_dir / "html_assets"
    output_dirs = ensure_output_report_dirs(config)
    reports_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    recession_periods = extract_recession_periods(panel.set_index("date")["current_recession"].astype(int))
    modes = enabled_snapshot_modes(config)
    realtime_panel = load_optional_panel(config, "realtime") if "realtime" in modes else pd.DataFrame()

    latest_predictions, latest_metrics = load_reporting_inputs(config, predictions, metrics, data_mode="latest_available")
    realtime_predictions, realtime_metrics = (
        load_reporting_inputs(config, predictions, metrics, data_mode="realtime") if "realtime" in modes else (pd.DataFrame(), pd.DataFrame())
    )

    latest_snapshot, latest_comparison, latest_quality = build_snapshot_tables(latest_predictions, latest_metrics, config, "latest_available")
    realtime_snapshot, realtime_comparison, realtime_quality = build_snapshot_tables(realtime_predictions, realtime_metrics, config, "realtime")
    mode_comparison = build_mode_comparison_table(latest_snapshot, realtime_snapshot, config)
    quality = pd.concat([latest_quality, realtime_quality], ignore_index=True, sort=False) if not latest_quality.empty or not realtime_quality.empty else pd.DataFrame()
    episode_summary = load_episode_summary(config)
    chart_paths = render_reporting_charts(
        latest_snapshot,
        latest_comparison,
        latest_predictions,
        realtime_snapshot,
        realtime_comparison,
        realtime_predictions,
        episode_summary,
        recession_periods,
        output_dirs,
    )
    write_reporting_tables(
        latest_snapshot,
        latest_comparison,
        realtime_snapshot,
        realtime_comparison,
        mode_comparison,
        quality,
        output_dirs,
    )

    combined_path = plot_combined_summary_chart(predictions, recession_periods, assets_dir / "combined_timeseries.png")
    chart_paths_html: list[tuple[str, str]] = [("Combined Baseline Time Series", combined_path.name)]
    for model_name in metrics["model_name"]:
        frame = predictions[predictions["model_name"] == model_name].copy()
        if frame.empty:
            continue
        output_path = assets_dir / f"{model_name}_timeseries.png"
        plot_model_summary_chart(frame, metrics, recession_periods, output_path)
        chart_paths_html.append((model_title(model_name), output_path.name))

    latest_table = latest_snapshot.drop(columns=["model_name"], errors="ignore").round(4).to_html(index=False, classes="summary-table") if not latest_snapshot.empty else "<p>No latest-available snapshot data available.</p>"
    realtime_table = realtime_snapshot.drop(columns=["model_name"], errors="ignore").round(4).to_html(index=False, classes="summary-table") if not realtime_snapshot.empty else "<p>No realtime snapshot data available.</p>"
    mode_table = mode_comparison.round(4).to_html(index=False, classes="metrics-table") if not mode_comparison.empty else "<p>No mode comparison available.</p>"
    latest_comparison_table = latest_comparison.round(4).to_html(index=False, classes="metrics-table") if not latest_comparison.empty else "<p>No latest-available model comparison data available.</p>"
    realtime_comparison_table = realtime_comparison.round(4).to_html(index=False, classes="metrics-table") if not realtime_comparison.empty else "<p>No realtime model comparison data available.</p>"
    quality_table = quality.round(4).to_html(index=False, classes="metrics-table") if not quality.empty else "<p>No model quality table available.</p>"
    metrics_table = metrics.round(4).to_html(index=False, classes="metrics-table")

    charts_html = "\n".join(
        f"<section class=\"chart-card\"><h2>{title}</h2><img src=\"html_assets/{filename}\" alt=\"{title}\"></section>"
        for title, filename in chart_paths_html
    )
    investor_html = "\n".join(
        [
            f"<section class=\"chart-card\"><h2>Latest Available Selected History</h2><img src=\"../outputs/reports/charts/{chart_paths['selected_probabilities_latest_available'].name}\" alt=\"Latest available selected history\"></section>",
            f"<section class=\"chart-card\"><h2>Realtime Selected History</h2><img src=\"../outputs/reports/charts/{chart_paths['selected_probabilities_realtime'].name}\" alt=\"Realtime selected history\"></section>",
            f"<section class=\"chart-card\"><h2>Latest Available Percentile Context</h2><img src=\"../outputs/reports/charts/{chart_paths['historical_percentiles_latest_available'].name}\" alt=\"Latest available percentiles\"></section>",
            f"<section class=\"chart-card\"><h2>Realtime Percentile Context</h2><img src=\"../outputs/reports/charts/{chart_paths['historical_percentiles_realtime'].name}\" alt=\"Realtime percentiles\"></section>",
            f"<section class=\"chart-card\"><h2>Latest Available Model Comparison</h2><img src=\"../outputs/reports/charts/{chart_paths['current_model_comparison_latest_available'].name}\" alt=\"Latest available model comparison\"></section>",
            f"<section class=\"chart-card\"><h2>Realtime Model Comparison</h2><img src=\"../outputs/reports/charts/{chart_paths['current_model_comparison_realtime'].name}\" alt=\"Realtime model comparison\"></section>",
            f"<section class=\"chart-card\"><h2>Episode Warning Timing</h2><img src=\"../outputs/reports/charts/{chart_paths['episode_warning_timing'].name}\" alt=\"Episode timing\"></section>",
        ]
    )

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Recession Risk Monitoring Summary</title>
  <style>
    body {{ font-family: Georgia, 'Times New Roman', serif; margin: 24px auto 48px; max-width: 1260px; color: #1c1c1c; line-height: 1.5; background: linear-gradient(180deg, #f7f2e8 0%, #f0ece4 100%); }}
    h1, h2, h3 {{ color: #1f2d3d; }}
    .hero {{ background: #17324d; color: #f8f3e8; padding: 24px 28px; border-radius: 16px; margin-bottom: 24px; }}
    .hero p {{ margin: 8px 0 0; color: #ddd4c5; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin: 24px 0; }}
    .card {{ background: rgba(255,255,255,0.9); border: 1px solid #d8d2c8; padding: 18px; border-radius: 14px; box-shadow: 0 8px 22px rgba(39,52,67,0.06); }}
    .summary-table, .metrics-table {{ border-collapse: collapse; width: 100%; margin: 16px 0 32px; background: rgba(255,255,255,0.92); }}
    .summary-table th, .summary-table td, .metrics-table th, .metrics-table td {{ border: 1px solid #d8d2c8; padding: 8px 10px; text-align: left; }}
    .summary-table th, .metrics-table th {{ background: #ebe4d8; }}
    .chart-card {{ background: rgba(255,255,255,0.92); padding: 18px; margin: 0 0 24px; border: 1px solid #d8d2c8; border-radius: 14px; box-shadow: 0 8px 22px rgba(39,52,67,0.06); }}
    img {{ width: 100%; height: auto; display: block; }}
    .note {{ color: #5f6b76; margin-top: 24px; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <section class=\"hero\">
    <h1>U.S. Recession Odds Monitor</h1>
    <p>Investor-facing snapshots are shown in both latest-available and realtime form, with quality-gated model selection and benchmark fallback when expanded models do not clear the governance thresholds.</p>
  </section>
  <h2>Current Snapshot</h2>
  <h3>Latest Available</h3>
  {latest_table}
  <h3>Realtime</h3>
  {realtime_table}
  <h3>Latest vs Realtime</h3>
  {mode_table}
  <section class=\"grid\">
    <section class=\"card\"><h2>Latest Available Regime</h2><p>{snapshot_overall_regime(latest_snapshot)}</p></section>
    <section class=\"card\"><h2>Realtime Regime</h2><p>{snapshot_overall_regime(realtime_snapshot)}</p></section>
    <section class=\"card\"><h2>Latest Available Signal Drivers</h2><p>{build_signal_driver_summary(panel, latest_snapshot, latest_comparison, mode_comparison).replace(chr(10), '<br>')}</p></section>
    <section class=\"card\"><h2>Realtime Signal Drivers</h2><p>{build_signal_driver_summary(realtime_panel, realtime_snapshot, realtime_comparison, mode_comparison).replace(chr(10), '<br>') if not realtime_panel.empty else 'Realtime signal summary unavailable.'}</p></section>
    <section class=\"card\"><h2>Model Disagreement</h2><p>{model_disagreement_text(latest_comparison)}</p></section>
    <section class=\"card\"><h2>Portfolio Interpretation</h2><p>{build_portfolio_interpretation(latest_snapshot, config).replace(chr(10), '<br>')}</p></section>
  </section>
  <h2>Snapshot Governance</h2>
  {quality_table}
  <h2>Current Model Comparison</h2>
  <h3>Latest Available</h3>
  {latest_comparison_table}
  <h3>Realtime</h3>
  {realtime_comparison_table}
  <h2>Investor-Facing Charts</h2>
  {investor_html}
  <h2>Baseline Metrics</h2>
  {metrics_table}
  <h2>Baseline Time-Series Charts</h2>
  {charts_html}
  <p class=\"note\">Recession periods are shaded in gray on time-series charts. Expanded-model probabilities are calibrated before investor-facing selection. Rule models remain threshold-based monitors.</p>
</body>
</html>
"""
    output_path = reports_dir / "recession_risk_summary.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


def load_optional_panel(config: dict, data_mode: str) -> pd.DataFrame:
    try:
        return load_monthly_panel(config, data_mode=data_mode)
    except FileNotFoundError:
        return pd.DataFrame()


def enabled_snapshot_modes(config: dict) -> list[str]:
    modes = config.get("reporting", {}).get("snapshot_modes", ["latest_available", "realtime"])
    return [str(mode) for mode in modes]


def plot_model_summary_chart(
    frame: pd.DataFrame,
    metrics: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    output_path: str | Path,
) -> Path:
    model_name = frame["model_name"].iloc[0]
    spec = MODEL_SPECS[model_name]
    metric_row = metrics.loc[metrics["model_name"] == model_name].iloc[0]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 4.5))
    plot_values = model_plot_values(frame)
    if spec["kind"] == "signal":
        ax.step(frame["date"], plot_values, where="post", linewidth=2, color=spec["color"])
        ax.set_ylim(-0.05, 1.05)
    else:
        ax.plot(frame["date"], plot_values, linewidth=2, color=spec["color"])
        threshold = spec["threshold"]
        if isinstance(threshold, (int, float)):
            ax.axhline(float(threshold), linestyle="--", color="#444444", alpha=0.7)
    for start, end in recession_periods:
        ax.axvspan(start, end + pd.offsets.MonthEnd(0), color="#d9d9d9", alpha=0.45)
    ax.set_title(str(spec["title"]))
    ax.set_ylabel(str(spec["ylabel"]))
    ax.grid(alpha=0.2)
    ax.text(
        0.99,
        0.96,
        format_metric_box(metric_row),
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "alpha": 0.9, "edgecolor": "#b8b0a3"},
    )
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_combined_summary_chart(
    predictions: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    for model_name, frame in predictions.groupby("model_name"):
        spec = MODEL_SPECS[model_name]
        ax.plot(frame["date"], model_plot_values(frame), linewidth=2, label=spec["title"], color=spec["color"])
    for start, end in recession_periods:
        ax.axvspan(start, end + pd.offsets.MonthEnd(0), color="#d9d9d9", alpha=0.35)
    ax.set_title("Combined Time Series")
    ax.set_ylabel("Normalized risk / signal")
    ax.set_ylim(-0.05, 1.05)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left", ncols=2)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def model_plot_values(frame: pd.DataFrame) -> pd.Series:
    model_name = frame["model_name"].iloc[0]
    if model_name == "yield_curve_inversion":
        return frame["signal"].astype(float)
    if model_name == "sahm_rule":
        return (frame["score"].astype(float) / 0.5).clip(lower=0.0, upper=1.0)
    return frame["score"].astype(float).clip(lower=0.0, upper=1.0)


def format_metric_box(metric_row: pd.Series) -> str:
    lines = [
        f"AUC: {metric_value(metric_row['auc'])}",
        f"Precision: {metric_value(metric_row['precision'])}",
        f"Recall: {metric_value(metric_row['recall'])}",
        f"Hit rate: {metric_value(metric_row['event_hit_rate'])}",
        f"Median timing: {metric_value(metric_row['median_timing_months'])}",
    ]
    return "\n".join(lines)


def metric_value(value) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"
