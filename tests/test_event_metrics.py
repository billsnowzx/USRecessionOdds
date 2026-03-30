from __future__ import annotations

import math

import pandas as pd

from recession_risk.backtest.event_metrics import build_event_scorecard, build_episode_summary, summarize_event_metrics
from recession_risk.backtest.thresholds import build_threshold_analysis


def test_event_scorecard_forecast_tracks_lead_and_false_alarms():
    predictions = pd.DataFrame(
        {
            "date": pd.to_datetime(["1999-11-01", "1999-12-01", "2000-01-01", "2000-02-01", "2000-03-01", "2000-04-01"]),
            "target_name": ["within_3m"] * 6,
            "horizon": [3] * 6,
            "model_name": ["forecast_model"] * 6,
            "score": [0.7, 0.8, 0.2, 0.1, 0.0, 0.0],
            "signal": [True, True, False, False, False, False],
            "split_name": ["holdout"] * 6,
            "actual": [0, 1, 1, 1, 0, 0],
        }
    )
    periods = [(pd.Timestamp("2000-01-01"), pd.Timestamp("2000-03-01"))]

    scorecard = build_event_scorecard(predictions, periods, event_mode="forecast", lookback_months=3)
    summary = summarize_event_metrics(predictions, periods, event_mode="forecast", lookback_months=3)
    episode_summary = build_episode_summary(scorecard)

    assert len(scorecard) == 1
    assert scorecard.loc[0, "first_warning_date"] == "1999-11-01"
    assert scorecard.loc[0, "timing_months"] == 2.0
    assert scorecard.loc[0, "false_alarm_months_before_episode"] == 0
    assert math.isclose(summary["event_hit_rate"], 1.0)
    assert math.isclose(summary["average_timing_months"], 2.0)
    assert episode_summary.loc[0, "episode_recall"] == 1.0


def test_threshold_analysis_emits_probability_model_rows():
    predictions = pd.DataFrame(
        {
            "date": pd.to_datetime(["2000-01-01", "2000-02-01", "2000-03-01", "2000-04-01"]),
            "target_name": ["within_3m"] * 4,
            "horizon": [3] * 4,
            "model_name": ["prob_model"] * 4,
            "score": [0.2, 0.4, 0.7, 0.9],
            "signal": [False, False, True, True],
            "split_name": ["holdout"] * 4,
            "test_start": ["2000-01-01"] * 4,
            "actual": [0, 0, 1, 1],
        }
    )
    periods = [(pd.Timestamp("2000-03-01"), pd.Timestamp("2000-05-01"))]
    config = {"thresholds": {"probability": 0.5}, "evaluation": {"thresholds": [0.25, 0.5, 0.75]}}

    analysis = build_threshold_analysis(predictions, periods, config)

    assert list(analysis["threshold"]) == [0.25, 0.5, 0.75]
    assert {"auc", "precision", "recall", "episode_recall", "max_false_alarm_streak"}.issubset(analysis.columns)
