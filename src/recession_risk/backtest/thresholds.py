from __future__ import annotations

import pandas as pd

from recession_risk.backtest.metrics import summarize_predictions


def build_threshold_analysis(
    predictions: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    config: dict,
) -> pd.DataFrame:
    thresholds = config.get("evaluation", {}).get("thresholds", [config["thresholds"]["probability"]])
    if predictions.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []

    for _, frame in predictions.groupby("model_name", dropna=False):
        if not is_probability_scored(frame):
            continue
        target_name = str(frame["target_name"].iloc[0])
        event_mode = "detect" if target_name == "current_recession" else "forecast"
        for threshold in thresholds:
            thresholded = frame.copy()
            thresholded["signal"] = thresholded["score"].astype(float) >= float(threshold)
            row = summarize_predictions(
                thresholded,
                recession_periods,
                event_mode=event_mode,
                probability_model=True,
            )
            row["threshold"] = float(threshold)
            rows.append(dict(row))

    return pd.DataFrame(rows)


def is_probability_scored(predictions: pd.DataFrame) -> bool:
    scores = predictions["score"].astype(float)
    return bool(scores.notna().all() and ((scores >= 0.0) & (scores <= 1.0)).all())
