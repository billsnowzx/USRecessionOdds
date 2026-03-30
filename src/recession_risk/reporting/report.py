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
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    recession_periods = extract_recession_periods(panel.set_index("date")["current_recession"].astype(int))
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
            "# Recession Risk Replication Report",
            "",
            "## Summary",
            "",
            "This report reproduces the four baseline measurements defined in the repository configuration.",
            "",
            "## Metrics",
            "",
            metrics.round(4).to_markdown(index=False),
            "",
            "## Figures",
            "",
            "![Term spread](figures/term_spread.png)",
            "",
            "![Yield curve probability](figures/yield_curve_probability.png)",
            "",
            "![ROC curves](figures/baseline_roc.png)",
            "",
            "![Yield curve calibration](figures/yield_curve_calibration.png)",
            "",
            "## Notes",
            "",
            "- Daily financial series are aggregated to monthly frequency before modeling.",
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
    reports_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    recession_periods = extract_recession_periods(panel.set_index("date")["current_recession"].astype(int))
    chart_paths: list[tuple[str, str]] = []

    combined_path = plot_combined_summary_chart(predictions, recession_periods, assets_dir / "combined_timeseries.png")
    chart_paths.append(("Combined Time Series", combined_path.name))

    for model_name in metrics["model_name"]:
        frame = predictions[predictions["model_name"] == model_name].copy()
        if frame.empty:
            continue
        output_path = assets_dir / f"{model_name}_timeseries.png"
        plot_model_summary_chart(frame, metrics, recession_periods, output_path)
        chart_paths.append((MODEL_SPECS[model_name]["title"], output_path.name))

    summary_rows = []
    for _, metric_row in metrics.iterrows():
        model_name = metric_row["model_name"]
        latest = predictions[predictions["model_name"] == model_name].sort_values("date").iloc[-1]
        summary_rows.append(
            {
                "Model": MODEL_SPECS[model_name]["title"],
                "Latest date": str(pd.Timestamp(latest["date"]).date()),
                "Latest score": round(float(latest["score"]), 4),
                "Latest signal": bool(latest["signal"]),
                "AUC": round(float(metric_row["auc"]), 4) if pd.notna(metric_row["auc"]) else "",
                "Precision": round(float(metric_row["precision"]), 4),
                "Recall": round(float(metric_row["recall"]), 4),
                "Event hit rate": round(float(metric_row["event_hit_rate"]), 4) if pd.notna(metric_row["event_hit_rate"]) else "",
                "Median timing (months)": round(float(metric_row["median_timing_months"]), 2) if pd.notna(metric_row["median_timing_months"]) else "",
            }
        )
    summary_table = pd.DataFrame(summary_rows).to_html(index=False, classes="summary-table")
    metrics_table = metrics.round(4).to_html(index=False, classes="metrics-table")

    charts_html = "\n".join(
        f"<section class=\"chart-card\"><h2>{title}</h2><img src=\"html_assets/{filename}\" alt=\"{title}\"></section>"
        for title, filename in chart_paths
    )

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>Recession Risk Time-Series Summary</title>
  <style>
    body {{ font-family: Georgia, 'Times New Roman', serif; margin: 32px auto; max-width: 1200px; color: #1c1c1c; line-height: 1.5; background: #f7f4ef; }}
    h1, h2 {{ color: #1f2d3d; }}
    .meta {{ margin-bottom: 24px; color: #4f5b66; }}
    .summary-table, .metrics-table {{ border-collapse: collapse; width: 100%; margin: 16px 0 32px; background: white; }}
    .summary-table th, .summary-table td, .metrics-table th, .metrics-table td {{ border: 1px solid #d8d2c8; padding: 8px 10px; text-align: left; }}
    .summary-table th, .metrics-table th {{ background: #ebe4d8; }}
    .chart-card {{ background: white; padding: 18px; margin: 0 0 24px; border: 1px solid #d8d2c8; box-shadow: 0 3px 10px rgba(0,0,0,0.04); }}
    img {{ width: 100%; height: auto; display: block; }}
    .note {{ color: #5f6b76; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>Recession Risk Time-Series Summary</h1>
  <p class=\"meta\">Generated from the baseline backtest outputs in this repository. The combined chart normalizes heterogeneous model outputs onto a comparable 0-1 view: probabilistic models use raw probability, the inversion rule uses the binary alarm, and the Sahm rule uses threshold-normalized gap capped at 1.</p>
  <h2>Snapshot Summary</h2>
  {summary_table}
  <h2>Baseline Metrics</h2>
  {metrics_table}
  {charts_html}
  <p class=\"note\">Recession periods are shaded in gray on all charts.</p>
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