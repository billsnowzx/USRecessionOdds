from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from recession_risk.backtest.event_metrics import summarize_event_metrics


@dataclass
class EventTimingResult:
    hit_rate: float
    median_months: float
    hits: int
    n_events: int


def summarize_predictions(
    predictions: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    event_mode: str,
    probability_model: bool,
) -> dict[str, float | int | str]:
    y_true = predictions["actual"].astype(int).to_numpy()
    signal = predictions["signal"].astype(bool).to_numpy()
    score = predictions["score"].astype(float).to_numpy()

    precision, recall, f1, false_positives = precision_recall_f1(y_true, signal)
    event_summary = summarize_event_metrics(
        predictions,
        recession_periods,
        event_mode=event_mode,
        lookback_months=int(predictions["horizon"].iloc[0]) if event_mode == "forecast" else None,
    )

    return {
        "model_name": predictions["model_name"].iloc[0],
        "target_name": predictions["target_name"].iloc[0],
        "horizon": int(predictions["horizon"].iloc[0]),
        "split_name": predictions["split_name"].iloc[0],
        "test_start": str(pd.Timestamp(predictions["test_start"].iloc[0]).date()),
        "auc": roc_auc(y_true, score),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_months": false_positives,
        "brier_score": brier_score(y_true, score) if probability_model else np.nan,
        "ece": expected_calibration_error(y_true, score) if probability_model else np.nan,
        **event_summary,
    }


def roc_auc(y_true, scores) -> float:
    y = pd.Series(y_true).astype(int)
    s = pd.Series(scores).astype(float)
    positives = int(y.sum())
    negatives = int((1 - y).sum())
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = s.rank(method="average")
    auc = (ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives)
    return float(auc)


def precision_recall_f1(y_true, signal) -> tuple[float, float, float, int]:
    y = np.asarray(y_true, dtype=int)
    pred = np.asarray(signal, dtype=bool)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return float(precision), float(recall), float(f1), fp


def brier_score(y_true, scores) -> float:
    y = np.asarray(y_true, dtype=float)
    s = np.asarray(scores, dtype=float)
    return float(np.mean(np.square(s - y)))


def expected_calibration_error(y_true, scores, n_bins: int = 10) -> float:
    curve = calibration_curve_data(y_true, scores, n_bins=n_bins)
    if curve.empty:
        return float("nan")
    return float((curve["bin_weight"] * (curve["avg_score"] - curve["avg_actual"]).abs()).sum())


def calibration_curve_data(y_true, scores, n_bins: int = 10) -> pd.DataFrame:
    frame = pd.DataFrame({"y_true": y_true, "score": scores}).dropna()
    if frame.empty:
        return pd.DataFrame(columns=["bin", "avg_score", "avg_actual", "count", "bin_weight"])

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    frame["bin"] = pd.cut(
        frame["score"].clip(0.0, 1.0),
        bins=bins,
        include_lowest=True,
        duplicates="drop",
    )
    grouped = frame.groupby("bin", observed=False).agg(
        avg_score=("score", "mean"),
        avg_actual=("y_true", "mean"),
        count=("y_true", "size"),
    )
    grouped = grouped[grouped["count"] > 0].reset_index()
    total = grouped["count"].sum()
    grouped["bin_weight"] = grouped["count"] / total if total else 0.0
    return grouped


def event_hit_rate(
    predictions: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    event_mode: str,
    lookback_months: int | None,
) -> EventTimingResult:
    frame = predictions.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    signal_dates = frame.loc[frame["signal"], "date"]
    if frame.empty:
        return EventTimingResult(float("nan"), float("nan"), 0, 0)

    min_date = frame["date"].min()
    max_date = frame["date"].max()
    timings: list[int] = []
    hits = 0
    eligible_events = 0

    for start, end in recession_periods:
        if event_mode == "forecast":
            if lookback_months is None:
                raise ValueError("Forecast mode requires lookback_months.")
            if start < min_date or start > max_date:
                continue
            eligible_events += 1
            window_start = start - pd.DateOffset(months=lookback_months)
            relevant = signal_dates[(signal_dates >= window_start) & (signal_dates < start)]
            if not relevant.empty:
                hits += 1
                timings.append(month_difference(relevant.iloc[0], start))
        else:
            if start > max_date or end < min_date:
                continue
            eligible_events += 1
            relevant = signal_dates[(signal_dates >= start) & (signal_dates <= end)]
            if not relevant.empty:
                hits += 1
                timings.append(month_difference(start, relevant.iloc[0]))

    return EventTimingResult(
        hit_rate=hits / eligible_events if eligible_events else float("nan"),
        median_months=float(np.median(timings)) if timings else float("nan"),
        hits=hits,
        n_events=eligible_events,
    )


def month_difference(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)
