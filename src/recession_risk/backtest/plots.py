from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from recession_risk.backtest.metrics import calibration_curve_data


def plot_series_with_recessions(
    series: pd.Series,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    output_path: str | Path,
    title: str,
    ylabel: str,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(series.index, series.values, color="#1f4e79", linewidth=2)
    for start, end in recession_periods:
        ax.axvspan(start, end + pd.offsets.MonthEnd(0), color="#d9d9d9", alpha=0.5)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_probability_over_time(
    frame: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    output_path: str | Path,
    title: str,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(frame["date"], frame["score"], color="#c44e52", linewidth=2)
    for start, end in recession_periods:
        ax.axvspan(start, end + pd.offsets.MonthEnd(0), color="#d9d9d9", alpha=0.5)
    ax.set_ylim(0.0, 1.0)
    ax.set_title(title)
    ax.set_ylabel("Probability")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_roc_curves(predictions: pd.DataFrame, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 6))
    for model_name, frame in predictions.groupby("model_name"):
        if frame["actual"].nunique() < 2:
            continue
        x_vals, y_vals = roc_curve(frame["actual"].to_numpy(), frame["score"].to_numpy())
        ax.plot(x_vals, y_vals, linewidth=2, label=model_name)
    ax.plot([0, 1], [0, 1], linestyle="--", color="black", alpha=0.5)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC curves")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_calibration(predictions: pd.DataFrame, output_path: str | Path, title: str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    curve = calibration_curve_data(predictions["actual"], predictions["score"])
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="black", alpha=0.5)
    ax.plot(curve["avg_score"], curve["avg_actual"], marker="o", linewidth=2, color="#55a868")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Observed frequency")
    ax.set_title(title)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def roc_curve(y_true, scores) -> tuple[np.ndarray, np.ndarray]:
    frame = pd.DataFrame({"y_true": y_true, "score": scores}).sort_values("score", ascending=False)
    positives = max(int(frame["y_true"].sum()), 1)
    negatives = max(int((1 - frame["y_true"]).sum()), 1)
    thresholds = frame["score"].drop_duplicates().to_numpy()
    tpr = [0.0]
    fpr = [0.0]
    for threshold in thresholds:
        pred = frame["score"] >= threshold
        tp = int(((pred == 1) & (frame["y_true"] == 1)).sum())
        fp = int(((pred == 1) & (frame["y_true"] == 0)).sum())
        tpr.append(tp / positives)
        fpr.append(fp / negatives)
    tpr.append(1.0)
    fpr.append(1.0)
    return np.array(fpr), np.array(tpr)