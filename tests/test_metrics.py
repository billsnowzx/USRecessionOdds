from __future__ import annotations

import math

import pandas as pd

from recession_risk.backtest.metrics import event_hit_rate, expected_calibration_error, month_difference, roc_auc


def test_event_hit_rate_forecast_lead_time():
    predictions = pd.DataFrame(
        {
            "date": pd.to_datetime(["2000-01-01", "2000-02-01", "2000-03-01", "2000-04-01"]),
            "signal": [False, True, False, False],
            "horizon": [3, 3, 3, 3],
        }
    )
    periods = [(pd.Timestamp("2000-04-01"), pd.Timestamp("2000-06-01"))]
    result = event_hit_rate(predictions, periods, event_mode="forecast", lookback_months=3)
    assert result.hit_rate == 1.0
    assert result.median_months == 2.0


def test_expected_calibration_error_is_zero_for_perfect_bins():
    y_true = [0, 0, 1, 1]
    scores = [0.0, 0.0, 1.0, 1.0]
    assert expected_calibration_error(y_true, scores, n_bins=2) == 0.0


def test_roc_auc_and_month_difference():
    assert math.isclose(roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]), 1.0)
    assert month_difference(pd.Timestamp("2000-01-01"), pd.Timestamp("2000-04-01")) == 3
