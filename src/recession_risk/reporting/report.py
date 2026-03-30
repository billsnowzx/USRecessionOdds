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
from recession_risk.reporting.snapshot import (
    build_portfolio_interpretation,
    build_signal_driver_summary,
    build_snapshot_tables,
    ensure_output_report_dirs,
    load_episode_summary,
    load_reporting_inputs,
    model_color,
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
    all_predictions, all_metrics = load_reporting_inputs(config, predictions, metrics)
    snapshot, comparison = build_snapshot_tables(all_predictions, all_metrics, config)
    episode_summary = load_episode_summary(config)
    chart_paths = render_reporting_charts(
        snapshot,
        comparison,
        all_predictions,
        episode_summary,
        recession_periods,
        output_dirs,
    )
    write_reporting_tables(snapshot, comparison, output_dirs)
    write_supporting_markdown(snapshot, comparison, output_dirs)

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

    report = "\n".join(
        [
            "# Recession Risk Monitoring Report",
            "",
            "## Current Snapshot",
            "",
            snapshot.drop(columns=["model_name"], errors="ignore").round(4).to_markdown(index=False) if not snapshot.empty else "No snapshot data available.",
            "",
            f"Overall regime: {snapshot_overall_regime(snapshot)}",
            "",
            "## Signal Drivers",
            "",
            build_signal_driver_summary(panel, snapshot, comparison),
            "",
            "## Current Model Comparison",
            "",
            comparison.round(4).to_markdown(index=False) if not comparison.empty else "No model comparison data available.",
            "",
            "## Historical Comparison",
            "",
            f"![Selected probabilities](../outputs/reports/charts/{chart_paths['selected_probabilities'].name})",
            "",
            f"![Historical percentiles](../outputs/reports/charts/{chart_paths['historical_percentiles'].name})",
            "",
            f"![Current model comparison](../outputs/reports/charts/{chart_paths['current_model_comparison'].name})",
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
            build_portfolio_interpretation(snapshot, config) if config.get("reporting", {}).get("include_portfolio_interpretation", True) else "Portfolio interpretation disabled in config.",
            "",
            "## Notes",
            "",
            "- Daily financial series are aggregated to monthly frequency before modeling.",
            "- The current snapshot prefers probability-scored models when multiple models exist for a target.",
            "- Yield-curve models are evaluated on expansion months for forward recession labels.",
            "- HY credit and Sahm rule are evaluated as recession-state detectors.",
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
    all_predictions, all_metrics = load_reporting_inputs(config, predictions, metrics)
    snapshot, comparison = build_snapshot_tables(all_predictions, all_metrics, config)
    episode_summary = load_episode_summary(config)
    phase5_charts = render_reporting_charts(
        snapshot,
        comparison,
        all_predictions,
        episode_summary,
        recession_periods,
        output_dirs,
    )
    chart_paths: list[tuple[str, str]] = []

    combined_path = plot_combined_summary_chart(predictions, recession_periods, assets_dir / "combined_timeseries.png")
    chart_paths.append(("Combined Time Series", combined_path.name))

    for model_name in metrics["model_name"]:
        frame = predictions[predictions["model_name"] == model_name].copy()
        if frame.empty:
            continue
        output_path = assets_dir / f"{model_name}_timeseries.png"
        plot_model_summary_chart(frame, metrics, recession_periods, output_path)
        chart_paths.append((model_title(model_name), output_path.name))

    summary_table = snapshot.drop(columns=["model_name"], errors="ignore").round(4).to_html(index=False, classes="summary-table")
    comparison_table = comparison.round(4).to_html(index=False, classes="metrics-table") if not comparison.empty else "<p>No model comparison data available.</p>"
    metrics_table = metrics.round(4).to_html(index=False, classes="metrics-table")

    charts_html = "\n".join(
        f"<section class=\"chart-card\"><h2>{title}</h2><img src=\"html_assets/{filename}\" alt=\"{title}\"></section>"
        for title, filename in chart_paths
    )
    phase5_html = "\n".join(
        [
            f"<section class=\"chart-card\"><h2>Selected Horizon History</h2><img src=\"../outputs/reports/charts/{phase5_charts['selected_probabilities'].name}\" alt=\"Selected horizon history\"></section>",
            f"<section class=\"chart-card\"><h2>Historical Percentile Context</h2><img src=\"../outputs/reports/charts/{phase5_charts['historical_percentiles'].name}\" alt=\"Historical percentiles\"></section>",
            f"<section class=\"chart-card\"><h2>Current Model Comparison</h2><img src=\"../outputs/reports/charts/{phase5_charts['current_model_comparison'].name}\" alt=\"Current model comparison\"></section>",
            f"<section class=\"chart-card\"><h2>Episode Warning Timing</h2><img src=\"../outputs/reports/charts/{phase5_charts['episode_warning_timing'].name}\" alt=\"Episode timing\"></section>",
        ]
    )

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Recession Risk Monitoring Summary</title>
  <style>
    body {{ font-family: Georgia, 'Times New Roman', serif; margin: 24px auto 48px; max-width: 1260px; color: #1c1c1c; line-height: 1.5; background: linear-gradient(180deg, #f7f2e8 0%, #f0ece4 100%); }}
    h1, h2 {{ color: #1f2d3d; }}
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
    <p>Selected models provide a rules-based snapshot for now, 3M, 6M, and 12M recession risk using the best saved model per target in this repository.</p>
  </section>
  <h2>Current Snapshot</h2>
  {summary_table}
  <section class=\"grid\">
    <section class=\"card\"><h2>Overall Regime</h2><p>{snapshot_overall_regime(snapshot)}</p></section>
    <section class=\"card\"><h2>Signal Drivers</h2><p>{build_signal_driver_summary(panel, snapshot, comparison).replace(chr(10), '<br>')}</p></section>
    <section class=\"card\"><h2>Model Disagreement</h2><p>{model_disagreement_text(comparison)}</p></section>
    <section class=\"card\"><h2>Portfolio Interpretation</h2><p>{build_portfolio_interpretation(snapshot, config).replace(chr(10), '<br>')}</p></section>
  </section>
  <h2>Current Model Comparison</h2>
  {comparison_table}
  <h2>Investor-Facing Charts</h2>
  {phase5_html}
  <h2>Baseline Metrics</h2>
  {metrics_table}
  <h2>Baseline Time-Series Charts</h2>
  {charts_html}
  <p class=\"note\">Recession periods are shaded in gray on time-series charts. Historical percentiles are relative to each selected model's own archive.</p>
</body>
</html>
"""
    output_path = reports_dir / "recession_risk_summary.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


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
        if spec["threshold"] is not None:
            ax.axhline(spec["threshold"], linestyle="--", color="#444444", alpha=0.7)
    for start, end in recession_periods:
        ax.axvspan(start, end + pd.offsets.MonthEnd(0), color="#d9d9d9", alpha=0.45)
    ax.set_title(spec["title"])
    ax.set_ylabel(spec["ylabel"])
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
