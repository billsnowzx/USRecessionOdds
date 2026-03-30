from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError

from recession_risk.backtest.model_selection import (
    apply_selection_gates,
    is_probability_model_name,
    sort_candidate_metrics,
)

TARGET_LABELS = {
    "current_recession": "P(recession now)",
    "within_3m": "P(recession within 3 months)",
    "within_6m": "P(recession within 6 months)",
    "within_12m": "P(recession within 12 months)",
}

TARGET_ORDER = ["current_recession", "within_3m", "within_6m", "within_12m"]
MODE_LABELS = {
    "latest_available": "Latest available",
    "realtime": "Realtime",
}

MODEL_COLORS = {
    "yield_curve_logit": "#b54d3e",
    "yield_curve_inversion": "#2f5d7c",
    "hy_credit_logit": "#356f52",
    "sahm_rule": "#7e654d",
    "multivariate_logit": "#006d77",
    "regularized_logit": "#577590",
    "ensemble": "#7a3e9d",
    "tree_boosting": "#a663cc",
}


def ensure_output_report_dirs(config: dict) -> dict[str, Path]:
    root = config["paths"]["outputs"] / "reports"
    dirs = {
        "root": root,
        "current_snapshot": root / "current_snapshot",
        "historical_comparison": root / "historical_comparison",
        "charts": root / "charts",
        "tables": root / "tables",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def load_reporting_inputs(
    config: dict,
    baseline_predictions: pd.DataFrame,
    baseline_metrics: pd.DataFrame,
    data_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    backtests_dir = config["paths"]["outputs"] / "backtests"
    if data_mode == "latest_available":
        predictions_frames = [baseline_predictions.copy()]
        metrics_frames = [baseline_metrics.copy()]
        optional_paths = [("expanded_predictions.csv", "expanded_metrics.csv")]
    else:
        predictions_frames = []
        metrics_frames = []
        optional_paths = [
            ("realtime_predictions.csv", "realtime_metrics.csv"),
            ("expanded_predictions_realtime.csv", "expanded_metrics_realtime.csv"),
        ]

    for prediction_name, metrics_name in optional_paths:
        prediction_path = backtests_dir / prediction_name
        metrics_path = backtests_dir / metrics_name
        if prediction_path.exists() and metrics_path.exists():
            try:
                prediction_frame = pd.read_csv(prediction_path)
                metrics_frame = pd.read_csv(metrics_path)
            except EmptyDataError:
                continue
            for column in [name for name in ["date", "forecast_date", "train_end", "test_start"] if name in prediction_frame.columns]:
                prediction_frame[column] = pd.to_datetime(prediction_frame[column], errors="coerce")
            predictions_frames.append(prediction_frame)
            metrics_frames.append(metrics_frame)

    predictions = pd.concat(predictions_frames, ignore_index=True, sort=False) if predictions_frames else pd.DataFrame()
    metrics = pd.concat(metrics_frames, ignore_index=True, sort=False) if metrics_frames else pd.DataFrame()
    if not metrics.empty:
        metrics = apply_selection_gates(metrics, config)
    return predictions, metrics


def build_snapshot_tables(
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    config: dict,
    data_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    snapshot_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []
    quality_rows: list[dict[str, object]] = []
    mode_label = MODE_LABELS.get(data_mode, data_mode.replace("_", " ").title())

    if metrics.empty or predictions.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    gated_metrics = apply_selection_gates(metrics, config) if "passes_selection_gates" not in metrics.columns else metrics.copy()
    if "is_benchmark" in gated_metrics.columns:
        gated_metrics["is_benchmark"] = gated_metrics["is_benchmark"].fillna(False).astype(bool)
    if "passes_selection_gates" in gated_metrics.columns:
        gated_metrics["passes_selection_gates"] = gated_metrics["passes_selection_gates"].fillna(False).astype(bool)

    for target_name in TARGET_ORDER:
        target_metrics = gated_metrics[gated_metrics["target_name"] == target_name].copy()
        if target_metrics.empty:
            continue
        target_metrics = sort_candidate_metrics(target_metrics)
        selected_row, fallback_reason = select_snapshot_model(target_metrics)

        for _, metric_row in target_metrics.iterrows():
            model_name = str(metric_row["model_name"])
            frame = predictions[predictions["model_name"] == model_name].sort_values("date").copy()
            if frame.empty:
                continue
            latest = frame.iloc[-1]
            normalized_history = normalized_model_values(frame)
            latest_probability = float(normalized_history.iloc[-1])
            selected = model_name == str(selected_row["model_name"])
            selection_status = "selected" if selected else ("eligible_candidate" if bool(metric_row["passes_selection_gates"]) else "rejected")
            quality_rows.append(
                {
                    "Mode": mode_label,
                    "Target": TARGET_LABELS.get(target_name, target_name),
                    "Model": model_title(model_name),
                    "Model family": model_family_label(model_name),
                    "Selected": selected,
                    "Selection status": selection_status,
                    "Quality gates": "pass" if bool(metric_row["passes_selection_gates"]) else "fail",
                    "Gate reasons": str(metric_row.get("selection_gate_reasons", "")),
                    "Fallback reason": fallback_reason if selected else "",
                    "AUC": safe_metric(metric_row.get("auc")),
                    "ECE": safe_metric(metric_row.get("ece")),
                    "Episode recall": safe_metric(metric_row.get("episode_recall")),
                    "Max false alarm streak": safe_metric(metric_row.get("max_false_alarm_streak")),
                    "Probability": latest_probability,
                }
            )
            comparison_rows.append(
                {
                    "Mode": mode_label,
                    "Target": TARGET_LABELS.get(target_name, target_name),
                    "Model": model_title(model_name),
                    "As of": str(pd.Timestamp(latest["date"]).date()),
                    "Probability": latest_probability,
                    "Raw score": float(latest.get("raw_score", latest["score"])),
                    "Calibrated score": float(latest["score"]),
                    "Historical percentile": percentile_rank(normalized_history, latest_probability),
                    "AUC": safe_metric(metric_row.get("auc")),
                    "Episode recall": safe_metric(metric_row.get("episode_recall")),
                    "Quality gates": "pass" if bool(metric_row["passes_selection_gates"]) else "fail",
                    "Gate reasons": str(metric_row.get("selection_gate_reasons", "")),
                    "Regime": classify_regime(latest_probability, config),
                }
            )

        selected_model_name = str(selected_row["model_name"])
        selected_frame = predictions[predictions["model_name"] == selected_model_name].sort_values("date").copy()
        if selected_frame.empty:
            continue
        latest = selected_frame.iloc[-1]
        normalized_history = normalized_model_values(selected_frame)
        latest_probability = float(normalized_history.iloc[-1])
        snapshot_rows.append(
            {
                "Mode": mode_label,
                "Target": TARGET_LABELS.get(target_name, target_name),
                "Selected model": model_title(selected_model_name),
                "As of": str(pd.Timestamp(latest["date"]).date()),
                "Probability": latest_probability,
                "Historical percentile": percentile_rank(normalized_history, latest_probability),
                "Regime": classify_regime(latest_probability, config),
                "Quality gates": "pass" if bool(selected_row["passes_selection_gates"]) else "fail",
                "Selection note": fallback_reason or "Selected from eligible candidates",
                "model_name": selected_model_name,
            }
        )

    snapshot = pd.DataFrame(snapshot_rows)
    comparison = pd.DataFrame(comparison_rows)
    quality = pd.DataFrame(quality_rows)
    categories = [TARGET_LABELS[item] for item in TARGET_ORDER]
    for frame in [snapshot, comparison, quality]:
        if not frame.empty and "Target" in frame.columns:
            frame["Target"] = pd.Categorical(frame["Target"], categories=categories, ordered=True)
            frame.sort_values("Target", inplace=True)
            frame.reset_index(drop=True, inplace=True)
    return snapshot, comparison, quality


def build_mode_comparison_table(latest_snapshot: pd.DataFrame, realtime_snapshot: pd.DataFrame, config: dict) -> pd.DataFrame:
    if latest_snapshot.empty and realtime_snapshot.empty:
        return pd.DataFrame()

    latest_frame = latest_snapshot.copy()
    realtime_frame = realtime_snapshot.copy()
    if latest_frame.empty:
        latest_frame = pd.DataFrame(columns=["Target", "Selected model", "As of", "Probability", "Regime", "Selection note"])
    if realtime_frame.empty:
        realtime_frame = pd.DataFrame(columns=["Target", "Selected model", "As of", "Probability", "Regime", "Selection note"])

    latest_frame = latest_frame.rename(
        columns={
            "Selected model": "Latest available model",
            "As of": "Latest available as of",
            "Probability": "Latest available probability",
            "Regime": "Latest available regime",
            "Selection note": "Latest available note",
        }
    ).drop(columns=["Mode", "Historical percentile", "Quality gates", "model_name"], errors="ignore")
    realtime_frame = realtime_frame.rename(
        columns={
            "Selected model": "Realtime model",
            "As of": "Realtime as of",
            "Probability": "Realtime probability",
            "Regime": "Realtime regime",
            "Selection note": "Realtime note",
        }
    ).drop(columns=["Mode", "Historical percentile", "Quality gates", "model_name"], errors="ignore")

    merged = latest_frame.merge(realtime_frame, on="Target", how="outer")
    merged["Probability delta"] = merged["Latest available probability"].astype(float) - merged["Realtime probability"].astype(float)
    threshold = float(config.get("reporting", {}).get("material_difference_threshold", 0.1))
    merged["Material gap"] = merged["Probability delta"].abs() >= threshold
    return merged.sort_values("Target").reset_index(drop=True)


def write_reporting_tables(
    latest_snapshot: pd.DataFrame,
    latest_comparison: pd.DataFrame,
    realtime_snapshot: pd.DataFrame,
    realtime_comparison: pd.DataFrame,
    mode_comparison: pd.DataFrame,
    quality: pd.DataFrame,
    dirs: dict[str, Path],
) -> None:
    latest_snapshot.drop(columns=["model_name"], errors="ignore").to_csv(dirs["tables"] / "current_snapshot.csv", index=False)
    latest_snapshot.drop(columns=["model_name"], errors="ignore").to_csv(dirs["tables"] / "current_snapshot_latest_available.csv", index=False)
    realtime_snapshot.drop(columns=["model_name"], errors="ignore").to_csv(dirs["tables"] / "current_snapshot_realtime.csv", index=False)
    latest_comparison.to_csv(dirs["tables"] / "model_comparison.csv", index=False)
    latest_comparison.to_csv(dirs["tables"] / "model_comparison_latest_available.csv", index=False)
    realtime_comparison.to_csv(dirs["tables"] / "model_comparison_realtime.csv", index=False)
    mode_comparison.to_csv(dirs["tables"] / "snapshot_mode_comparison.csv", index=False)
    quality.to_csv(dirs["tables"] / "model_selection_quality.csv", index=False)


def write_supporting_markdown(
    latest_snapshot: pd.DataFrame,
    latest_comparison: pd.DataFrame,
    realtime_snapshot: pd.DataFrame,
    realtime_comparison: pd.DataFrame,
    mode_comparison: pd.DataFrame,
    quality: pd.DataFrame,
    chart_paths: dict[str, Path],
    dirs: dict[str, Path],
) -> None:
    (dirs["current_snapshot"] / "current_snapshot.md").write_text(
        "\n".join(
            [
                "# Current Snapshot",
                "",
                "## Latest Available",
                "",
                latest_snapshot.drop(columns=["model_name"], errors="ignore").round(4).to_markdown(index=False) if not latest_snapshot.empty else "No latest-available snapshot data available.",
                "",
                "## Realtime",
                "",
                realtime_snapshot.drop(columns=["model_name"], errors="ignore").round(4).to_markdown(index=False) if not realtime_snapshot.empty else "No realtime snapshot data available.",
                "",
                "## Mode Comparison",
                "",
                mode_comparison.round(4).to_markdown(index=False) if not mode_comparison.empty else "No mode comparison available.",
                "",
                f"![Latest available selected history](../charts/{chart_paths['selected_probabilities_latest_available'].name})",
                "",
                f"![Realtime selected history](../charts/{chart_paths['selected_probabilities_realtime'].name})",
            ]
        ),
        encoding="utf-8",
    )
    (dirs["historical_comparison"] / "historical_comparison.md").write_text(
        "\n".join(
            [
                "# Historical Comparison",
                "",
                "## Latest Available Model Comparison",
                "",
                latest_comparison.round(4).to_markdown(index=False) if not latest_comparison.empty else "No latest-available model comparison data available.",
                "",
                "## Realtime Model Comparison",
                "",
                realtime_comparison.round(4).to_markdown(index=False) if not realtime_comparison.empty else "No realtime model comparison data available.",
                "",
                "## Model Quality Governance",
                "",
                quality.round(4).to_markdown(index=False) if not quality.empty else "No quality table available.",
                "",
                f"![Latest available percentiles](../charts/{chart_paths['historical_percentiles_latest_available'].name})",
                "",
                f"![Realtime percentiles](../charts/{chart_paths['historical_percentiles_realtime'].name})",
                "",
                f"![Episode warning timing](../charts/{chart_paths['episode_warning_timing'].name})",
            ]
        ),
        encoding="utf-8",
    )


def load_episode_summary(config: dict) -> pd.DataFrame:
    backtests_dir = config["paths"]["outputs"] / "backtests"
    frames: list[pd.DataFrame] = []
    for name in [
        "baseline_episode_summary.csv",
        "expanded_episode_summary.csv",
        "realtime_episode_summary.csv",
        "expanded_realtime_episode_summary.csv",
    ]:
        path = backtests_dir / name
        if path.exists():
            frame = pd.read_csv(path)
            if frame.empty:
                continue
            frame["source_file"] = name
            frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def render_reporting_charts(
    latest_snapshot: pd.DataFrame,
    latest_comparison: pd.DataFrame,
    latest_predictions: pd.DataFrame,
    realtime_snapshot: pd.DataFrame,
    realtime_comparison: pd.DataFrame,
    realtime_predictions: pd.DataFrame,
    episode_summary: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    dirs: dict[str, Path],
) -> dict[str, Path]:
    return {
        "selected_probabilities_latest_available": plot_selected_probability_history(latest_snapshot, latest_predictions, recession_periods, dirs["charts"] / "selected_probabilities_latest_available.png", "Latest available selected probabilities"),
        "selected_probabilities_realtime": plot_selected_probability_history(realtime_snapshot, realtime_predictions, recession_periods, dirs["charts"] / "selected_probabilities_realtime.png", "Realtime selected probabilities"),
        "historical_percentiles_latest_available": plot_historical_percentiles(latest_snapshot, dirs["charts"] / "historical_percentiles_latest_available.png", "Latest available readings vs historical range"),
        "historical_percentiles_realtime": plot_historical_percentiles(realtime_snapshot, dirs["charts"] / "historical_percentiles_realtime.png", "Realtime readings vs historical range"),
        "current_model_comparison_latest_available": plot_current_model_comparison(latest_comparison, dirs["charts"] / "current_model_comparison_latest_available.png", "Latest available model comparison"),
        "current_model_comparison_realtime": plot_current_model_comparison(realtime_comparison, dirs["charts"] / "current_model_comparison_realtime.png", "Realtime model comparison"),
        "episode_warning_timing": plot_episode_warning_timing(episode_summary, dirs["charts"] / "episode_warning_timing.png"),
    }


def build_signal_driver_summary(panel: pd.DataFrame, snapshot: pd.DataFrame, comparison: pd.DataFrame, mode_comparison: pd.DataFrame | None = None) -> str:
    if panel.empty:
        return "- No panel data available."
    latest = panel.sort_values("date").iloc[-1]
    prior = panel.sort_values("date").iloc[max(len(panel) - 7, 0)]
    parts = [
        term_spread_text(latest, prior),
        hy_spread_text(latest, prior),
        sahm_gap_text(latest, prior),
        risk_trend_text(snapshot),
        model_disagreement_text(comparison),
    ]
    if mode_comparison is not None and not mode_comparison.empty:
        parts.append(mode_gap_text(mode_comparison))
    return "\n".join(f"- {part}" for part in parts if part)


def build_portfolio_interpretation(snapshot: pd.DataFrame, config: dict) -> str:
    if snapshot.empty:
        return "- No snapshot probabilities available."
    max_probability = float(snapshot["Probability"].max())
    regime = classify_regime(max_probability, config)
    if regime == "low risk":
        return "\n".join(
            [
                "- Equities: cyclical exposure can stay supported.",
                "- Duration: neutral duration still fits.",
                "- Credit beta: no acute stress signal is dominating.",
                "- Defensives / cash: liquidity can stay moderate rather than dominant.",
            ]
        )
    if regime == "rising risk":
        return "\n".join(
            [
                "- Equities: lean toward quality and earnings resilience.",
                "- Duration: some extra duration ballast becomes more useful.",
                "- Credit beta: lower-quality spread exposure deserves more caution.",
                "- Defensives / cash: optionality and liquidity buffers gain value.",
            ]
        )
    if regime == "elevated risk":
        return "\n".join(
            [
                "- Equities: cyclical beta becomes less forgiving.",
                "- Duration: high-quality duration is more useful as insurance.",
                "- Credit beta: prefer quality over carry-chasing.",
                "- Defensives / cash: larger dry powder is easier to justify.",
            ]
        )
    return "\n".join(
        [
            "- Equities: downside sensitivity is high and preservation matters more.",
            "- Duration: high-quality duration is the clearest macro hedge in this template.",
            "- Credit beta: keep a defensive stance toward lower-quality credit.",
            "- Defensives / cash: liquidity should carry more of the allocation burden.",
        ]
    )


def plot_selected_probability_history(
    snapshot: pd.DataFrame,
    predictions: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    output_path: str | Path,
    title: str,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    if snapshot.empty or predictions.empty:
        ax.text(0.5, 0.5, "No selected history available", ha="center", va="center")
    else:
        for _, row in snapshot.iterrows():
            model_name = row["model_name"]
            frame = predictions[predictions["model_name"] == model_name].sort_values("date")
            if frame.empty:
                continue
            ax.plot(frame["date"], normalized_model_values(frame), linewidth=2, label=str(row["Target"]), color=model_color(model_name))
    for start, end in recession_periods:
        ax.axvspan(start, end + pd.offsets.MonthEnd(0), color="#d8d8d8", alpha=0.35)
    ax.set_ylim(-0.02, 1.02)
    ax.set_title(title)
    ax.set_ylabel("Normalized probability")
    ax.grid(alpha=0.2)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_historical_percentiles(snapshot: pd.DataFrame, output_path: str | Path, title: str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    if snapshot.empty:
        ax.text(0.5, 0.5, "No snapshot available", ha="center", va="center")
    else:
        labels = snapshot["Target"].astype(str).tolist()
        values = snapshot["Historical percentile"].astype(float).to_numpy()
        colors = [model_color(model_name) for model_name in snapshot["model_name"]]
        ax.bar(labels, values, color=colors)
    ax.set_ylim(0.0, 1.0)
    ax.set_title(title)
    ax.set_ylabel("Percentile of own history")
    ax.grid(axis="y", alpha=0.2)
    fig.autofmt_xdate(rotation=15)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_current_model_comparison(comparison: pd.DataFrame, output_path: str | Path, title: str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    if comparison.empty:
        ax.text(0.5, 0.5, "No model comparison data available", ha="center", va="center")
    else:
        labels = [f"{target}\n{model}" for target, model in zip(comparison["Target"], comparison["Model"])]
        ax.bar(labels, comparison["Probability"].astype(float).to_numpy(), color=[model_color_from_title(title_value) for title_value in comparison["Model"]])
        ax.set_ylim(0.0, 1.0)
        ax.grid(axis="y", alpha=0.2)
    ax.set_title(title)
    ax.set_ylabel("Normalized probability")
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_episode_warning_timing(episode_summary: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    if episode_summary.empty:
        ax.text(0.5, 0.5, "No episode summary data available", ha="center", va="center")
    else:
        frame = episode_summary.sort_values(["event_mode", "average_timing_months"], ascending=[True, False])
        labels = [f"{model_title(model)} ({'lead' if mode == 'forecast' else 'lag'})" for model, mode in zip(frame["model_name"], frame["event_mode"])]
        values = frame["average_timing_months"].fillna(0.0).astype(float).to_numpy()
        ax.barh(labels, values, color=[model_color(model_name) for model_name in frame["model_name"]])
        ax.grid(axis="x", alpha=0.2)
    ax.set_title("Episode timing by model")
    ax.set_xlabel("Average lead or lag months")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def classify_regime(probability: float, config: dict) -> str:
    if pd.isna(probability):
        return "unclassified"
    for bucket in config.get("reporting", {}).get("regime_buckets", []):
        if float(probability) <= float(bucket["max_probability"]):
            return str(bucket["label"])
    return "unclassified"


def snapshot_overall_regime(snapshot: pd.DataFrame) -> str:
    if snapshot.empty:
        return "unclassified"
    max_row = snapshot.sort_values("Probability", ascending=False).iloc[0]
    return f"{max_row['Regime']} (driven by {max_row['Target']})"


def model_disagreement_text(comparison: pd.DataFrame) -> str:
    if comparison.empty:
        return "Model disagreement is unavailable."
    per_target = comparison.groupby("Target", observed=False)["Probability"].agg(
        lambda values: float(np.max(values) - np.min(values)) if len(values) > 1 else 0.0
    )
    average_range = float(per_target.mean()) if not per_target.empty else 0.0
    if average_range >= 0.25:
        return "Model disagreement is high; available models diverge materially."
    if average_range >= 0.10:
        return "Model disagreement is moderate; direction is shared but conviction differs."
    return "Model disagreement is low; available models are broadly aligned."


def mode_gap_text(mode_comparison: pd.DataFrame) -> str:
    if mode_comparison.empty:
        return "Realtime comparison is unavailable."
    if bool(mode_comparison["Material gap"].fillna(False).any()):
        targets = ", ".join(mode_comparison.loc[mode_comparison["Material gap"], "Target"].astype(str))
        return f"Latest-available and realtime snapshots differ materially for {targets}."
    return "Latest-available and realtime snapshots are broadly aligned."


def risk_trend_text(snapshot: pd.DataFrame) -> str:
    if snapshot.empty:
        return "Aggregate risk trend is unavailable."
    average_probability = float(snapshot["Probability"].mean())
    if average_probability >= 0.6:
        return "Aggregate recession risk is high across the selected horizons."
    if average_probability >= 0.35:
        return "Aggregate recession risk is elevated rather than benign."
    if average_probability >= 0.15:
        return "Aggregate recession risk is rising but not yet extreme."
    return "Aggregate recession risk remains in the lower part of its configured range."


def term_spread_text(latest: pd.Series, prior: pd.Series) -> str:
    if pd.isna(latest.get("term_spread")):
        return ""
    level = float(latest["term_spread"])
    delta = level - float(prior["term_spread"]) if pd.notna(prior.get("term_spread")) else np.nan
    if level < 0:
        trend = "deepening" if not pd.isna(delta) and delta < 0 else "still inverted"
        return f"The term spread is negative at {level:.2f}, keeping the curve {trend}."
    trend = "steepening" if not pd.isna(delta) and delta > 0 else "flatter than six months ago"
    return f"The term spread is positive at {level:.2f}, but the curve is {trend}."


def hy_spread_text(latest: pd.Series, prior: pd.Series) -> str:
    if pd.isna(latest.get("BAMLH0A0HYM2")):
        return ""
    level = float(latest["BAMLH0A0HYM2"])
    delta = level - float(prior["BAMLH0A0HYM2"]) if pd.notna(prior.get("BAMLH0A0HYM2")) else np.nan
    if level >= 5.5:
        return f"HY spreads are wide at {level:.2f}, consistent with tighter financial conditions."
    if level >= 4.0:
        return f"HY spreads are moderately wide at {level:.2f}; credit is not fully relaxed."
    trend = "widening" if not pd.isna(delta) and delta > 0 else "contained"
    return f"HY spreads are relatively contained at {level:.2f}, with the recent direction {trend}."


def sahm_gap_text(latest: pd.Series, prior: pd.Series) -> str:
    if pd.isna(latest.get("sahm_gap")):
        return ""
    level = float(latest["sahm_gap"])
    delta = level - float(prior["sahm_gap"]) if pd.notna(prior.get("sahm_gap")) else np.nan
    if level >= 0.5:
        return f"The Sahm gap is {level:.2f}, above the classic threshold."
    if level >= 0.25:
        return f"The Sahm gap is {level:.2f}, below the trigger but no longer comfortably benign."
    trend = "rising" if not pd.isna(delta) and delta > 0 else "stable to softer"
    return f"The Sahm gap is {level:.2f}, still below the recession trigger and {trend}."


def normalized_model_values(frame: pd.DataFrame) -> pd.Series:
    model_name = normalize_model_key(str(frame["model_name"].iloc[0]))
    if model_name == "yield_curve_inversion":
        return frame["signal"].astype(float).clip(lower=0.0, upper=1.0)
    if model_name == "sahm_rule":
        return (frame["score"].astype(float) / 0.5).clip(lower=0.0, upper=1.0)
    return frame["score"].astype(float).clip(lower=0.0, upper=1.0)


def percentile_rank(history: pd.Series, latest_value: float) -> float:
    series = pd.Series(history).dropna().astype(float)
    if series.empty:
        return float("nan")
    return float((series <= float(latest_value)).mean())


def select_snapshot_model(target_metrics: pd.DataFrame) -> tuple[pd.Series, str]:
    expanded_candidates = target_metrics[(~target_metrics["is_benchmark"].astype(bool)) & (target_metrics["passes_selection_gates"].astype(bool))]
    if not expanded_candidates.empty:
        return expanded_candidates.iloc[0], ""
    benchmark_candidates = sort_candidate_metrics(target_metrics[target_metrics["is_benchmark"].astype(bool)])
    if benchmark_candidates.empty:
        return target_metrics.iloc[0], "No benchmark candidate available; using best available model."
    return benchmark_candidates.iloc[0], "No expanded model passed quality gates; falling back to benchmark."


def is_probability_model(model_name: str) -> bool:
    return is_probability_model_name(model_name)


def model_title(model_name: str) -> str:
    normalized = normalize_model_key(model_name)
    words = re.sub(r"[_\-]+", " ", normalized).split()
    formatted = []
    for word in words:
        lowered = word.lower()
        if lowered == "hy":
            formatted.append("HY")
        elif lowered in {"3m", "6m", "12m"}:
            formatted.append(word.upper())
        else:
            formatted.append(word.capitalize())
    if str(model_name).endswith("_realtime"):
        formatted.append("(Realtime)")
    return " ".join(formatted)


def model_family_label(model_name: str) -> str:
    normalized = normalize_model_key(model_name)
    if normalized in {"yield_curve_logit", "yield_curve_inversion", "hy_credit_logit", "sahm_rule"}:
        return "Benchmark"
    if normalized.startswith("ensemble"):
        return "Ensemble"
    if normalized.startswith("tree_boosting"):
        return "Tree model"
    return "Expanded logit"


def normalize_model_key(model_name: str) -> str:
    name = str(model_name)
    return name[:-9] if name.endswith("_realtime") else name


def model_color(model_name: str) -> str:
    normalized = normalize_model_key(model_name)
    for prefix, color in MODEL_COLORS.items():
        if normalized.startswith(prefix):
            return color
    return "#4c6a92"


def model_color_from_title(title: str) -> str:
    normalized_title = title.replace(" (Realtime)", "")
    for model_key in MODEL_COLORS:
        if model_title(model_key) == normalized_title:
            return MODEL_COLORS[model_key]
    return "#4c6a92"


def safe_metric(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")
