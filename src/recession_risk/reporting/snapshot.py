from __future__ import annotations

from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TARGET_LABELS = {
    "current_recession": "P(recession now)",
    "within_3m": "P(recession within 3 months)",
    "within_6m": "P(recession within 6 months)",
    "within_12m": "P(recession within 12 months)",
}

TARGET_ORDER = ["current_recession", "within_3m", "within_6m", "within_12m"]

MODEL_COLORS = {
    "yield_curve_logit": "#b54d3e",
    "yield_curve_inversion": "#2f5d7c",
    "hy_credit_logit": "#356f52",
    "sahm_rule": "#7e654d",
    "multivariate_logit_within_3m": "#006d77",
    "multivariate_logit_within_6m": "#1d7874",
    "multivariate_logit_within_12m": "#3a7d44",
    "multivariate_logit_current_recession": "#7b2d26",
    "regularized_logit_within_3m": "#4d908e",
    "regularized_logit_within_6m": "#577590",
    "regularized_logit_within_12m": "#90be6d",
    "regularized_logit_current_recession": "#bc6c25",
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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions_frames = [baseline_predictions.copy()]
    metrics_frames = [baseline_metrics.copy()]
    backtests_dir = config["paths"]["outputs"] / "backtests"

    optional_paths = [
        ("expanded_predictions.csv", "expanded_metrics.csv"),
    ]
    for prediction_name, metrics_name in optional_paths:
        prediction_path = backtests_dir / prediction_name
        metrics_path = backtests_dir / metrics_name
        if prediction_path.exists() and metrics_path.exists():
            prediction_frame = pd.read_csv(prediction_path)
            metrics_frame = pd.read_csv(metrics_path)
            for column in [name for name in ["date", "forecast_date", "train_end", "test_start"] if name in prediction_frame.columns]:
                prediction_frame[column] = pd.to_datetime(prediction_frame[column], errors="coerce")
            predictions_frames.append(prediction_frame)
            metrics_frames.append(metrics_frame)

    return (
        pd.concat(predictions_frames, ignore_index=True, sort=False),
        pd.concat(metrics_frames, ignore_index=True, sort=False),
    )


def build_snapshot_tables(
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    snapshot_rows: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []

    for target_name in TARGET_ORDER:
        target_metrics = metrics[metrics["target_name"] == target_name].copy()
        if target_metrics.empty:
            continue
        target_metrics["probability_model"] = target_metrics["model_name"].apply(is_probability_model)
        target_metrics = target_metrics.sort_values(
            ["probability_model", "auc", "event_hit_rate", "precision"],
            ascending=[False, False, False, False],
        )

        for _, metric_row in target_metrics.iterrows():
            model_name = metric_row["model_name"]
            frame = predictions[predictions["model_name"] == model_name].sort_values("date").copy()
            if frame.empty:
                continue
            latest = frame.iloc[-1]
            normalized_history = normalized_model_values(frame)
            latest_probability = float(normalized_history.iloc[-1])
            comparison_rows.append(
                {
                    "Target": TARGET_LABELS.get(target_name, target_name),
                    "Model": model_title(model_name),
                    "As of": str(pd.Timestamp(latest["date"]).date()),
                    "Probability": latest_probability,
                    "Raw score": float(latest["score"]),
                    "Historical percentile": percentile_rank(normalized_history, latest_probability),
                    "AUC": float(metric_row["auc"]) if pd.notna(metric_row["auc"]) else np.nan,
                    "Episode recall": float(metric_row["episode_recall"]) if pd.notna(metric_row.get("episode_recall")) else np.nan,
                    "Regime": classify_regime(latest_probability, config),
                }
            )

        selected_model_name = target_metrics.iloc[0]["model_name"]
        selected_frame = predictions[predictions["model_name"] == selected_model_name].sort_values("date").copy()
        if selected_frame.empty:
            continue
        latest = selected_frame.iloc[-1]
        normalized_history = normalized_model_values(selected_frame)
        latest_probability = float(normalized_history.iloc[-1])
        snapshot_rows.append(
            {
                "Target": TARGET_LABELS.get(target_name, target_name),
                "Selected model": model_title(selected_model_name),
                "As of": str(pd.Timestamp(latest["date"]).date()),
                "Probability": latest_probability,
                "Historical percentile": percentile_rank(normalized_history, latest_probability),
                "Regime": classify_regime(latest_probability, config),
                "model_name": selected_model_name,
            }
        )

    snapshot = pd.DataFrame(snapshot_rows)
    comparison = pd.DataFrame(comparison_rows)
    categories = [TARGET_LABELS[item] for item in TARGET_ORDER]
    if not snapshot.empty:
        snapshot["Target"] = pd.Categorical(snapshot["Target"], categories=categories, ordered=True)
        snapshot = snapshot.sort_values("Target").reset_index(drop=True)
    if not comparison.empty:
        comparison["Target"] = pd.Categorical(comparison["Target"], categories=categories, ordered=True)
        comparison = comparison.sort_values(["Target", "AUC"], ascending=[True, False]).reset_index(drop=True)
    return snapshot, comparison


def write_reporting_tables(snapshot: pd.DataFrame, comparison: pd.DataFrame, dirs: dict[str, Path]) -> None:
    snapshot.drop(columns=["model_name"], errors="ignore").to_csv(dirs["tables"] / "current_snapshot.csv", index=False)
    comparison.to_csv(dirs["tables"] / "model_comparison.csv", index=False)


def write_supporting_markdown(snapshot: pd.DataFrame, comparison: pd.DataFrame, dirs: dict[str, Path]) -> None:
    (dirs["current_snapshot"] / "current_snapshot.md").write_text(
        "\n".join(
            [
                "# Current Snapshot",
                "",
                snapshot.drop(columns=["model_name"], errors="ignore").round(4).to_markdown(index=False),
                "",
                f"Overall regime: {snapshot_overall_regime(snapshot)}",
                "",
                "![Historical Percentiles](../charts/historical_percentiles.png)",
            ]
        ),
        encoding="utf-8",
    )
    (dirs["historical_comparison"] / "historical_comparison.md").write_text(
        "\n".join(
            [
                "# Historical Comparison",
                "",
                comparison.round(4).to_markdown(index=False),
                "",
                "![Selected Probabilities](../charts/selected_probabilities.png)",
                "",
                "![Current Model Comparison](../charts/current_model_comparison.png)",
                "",
                "![Episode Warning Timing](../charts/episode_warning_timing.png)",
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
    ]:
        path = backtests_dir / name
        if path.exists():
            frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def render_reporting_charts(
    snapshot: pd.DataFrame,
    comparison: pd.DataFrame,
    predictions: pd.DataFrame,
    episode_summary: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    dirs: dict[str, Path],
) -> dict[str, Path]:
    return {
        "selected_probabilities": plot_selected_probability_history(snapshot, predictions, recession_periods, dirs["charts"] / "selected_probabilities.png"),
        "historical_percentiles": plot_historical_percentiles(snapshot, dirs["charts"] / "historical_percentiles.png"),
        "current_model_comparison": plot_current_model_comparison(comparison, dirs["charts"] / "current_model_comparison.png"),
        "episode_warning_timing": plot_episode_warning_timing(episode_summary, dirs["charts"] / "episode_warning_timing.png"),
    }


def build_signal_driver_summary(panel: pd.DataFrame, snapshot: pd.DataFrame, comparison: pd.DataFrame) -> str:
    latest = panel.sort_values("date").iloc[-1]
    prior = panel.sort_values("date").iloc[max(len(panel) - 7, 0)]
    parts = [
        term_spread_text(latest, prior),
        hy_spread_text(latest, prior),
        sahm_gap_text(latest, prior),
        risk_trend_text(snapshot),
        model_disagreement_text(comparison),
    ]
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
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    for _, row in snapshot.iterrows():
        model_name = row["model_name"]
        frame = predictions[predictions["model_name"] == model_name].sort_values("date")
        if frame.empty:
            continue
        ax.plot(frame["date"], normalized_model_values(frame), linewidth=2, label=str(row["Target"]), color=model_color(model_name))
    for start, end in recession_periods:
        ax.axvspan(start, end + pd.offsets.MonthEnd(0), color="#d8d8d8", alpha=0.35)
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Selected Nowcast and Forward Recession Probabilities")
    ax.set_ylabel("Normalized probability")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_historical_percentiles(snapshot: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    labels = snapshot["Target"].astype(str).tolist() if not snapshot.empty else []
    values = snapshot["Historical percentile"].astype(float).to_numpy() if not snapshot.empty else np.array([])
    colors = [model_color(model_name) for model_name in snapshot["model_name"]] if "model_name" in snapshot.columns else []
    ax.bar(labels, values, color=colors)
    ax.set_ylim(0.0, 1.0)
    ax.set_title("Current Readings vs Historical Range")
    ax.set_ylabel("Percentile of own history")
    ax.grid(axis="y", alpha=0.2)
    fig.autofmt_xdate(rotation=15)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_current_model_comparison(comparison: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    if comparison.empty:
        ax.text(0.5, 0.5, "No model comparison data available", ha="center", va="center")
    else:
        labels = [f"{target}\n{model}" for target, model in zip(comparison["Target"], comparison["Model"])]
        ax.bar(labels, comparison["Probability"].astype(float).to_numpy(), color=[model_color_from_title(title) for title in comparison["Model"]])
        ax.set_ylim(0.0, 1.0)
        ax.grid(axis="y", alpha=0.2)
    ax.set_title("Current Reading by Available Model")
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
    ax.set_title("Episode Timing by Model")
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
    model_name = str(frame["model_name"].iloc[0])
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


def is_probability_model(model_name: str) -> bool:
    lowered = str(model_name).lower()
    return any(token in lowered for token in ["logit", "multivariate", "regularized"])


def model_title(model_name: str) -> str:
    words = re.sub(r"[_\-]+", " ", str(model_name)).split()
    formatted = []
    for word in words:
        lowered = word.lower()
        if lowered == "hy":
            formatted.append("HY")
        elif lowered in {"3m", "6m", "12m"}:
            formatted.append(word.upper())
        else:
            formatted.append(word.capitalize())
    return " ".join(formatted)


def model_color(model_name: str) -> str:
    return MODEL_COLORS.get(str(model_name), "#4c6a92")


def model_color_from_title(title: str) -> str:
    for model_name in MODEL_COLORS:
        if model_title(model_name) == title:
            return MODEL_COLORS[model_name]
    return "#4c6a92"
