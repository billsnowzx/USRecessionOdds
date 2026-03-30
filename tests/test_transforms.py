from __future__ import annotations

import pandas as pd

from recession_risk.features.transforms import aggregate_to_monthly, compute_sahm_gap, compute_term_spread


def test_aggregate_to_monthly_mean():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-01-15", "2020-02-01"]),
            "value": [1.0, 3.0, 5.0],
        }
    )
    result = aggregate_to_monthly(frame, "value", "mean")
    assert result.loc[pd.Timestamp("2020-01-01")] == 2.0
    assert result.loc[pd.Timestamp("2020-02-01")] == 5.0


def test_compute_term_spread():
    panel = pd.DataFrame({"DGS10": [4.0, 5.0], "DTB3": [3.0, 4.5]})
    spread = compute_term_spread(panel)
    assert spread.tolist() == [1.0, 0.5]


def test_compute_sahm_gap_matches_hand_worked_example():
    unrate = pd.Series([4.0] * 12 + [4.2, 4.4, 4.6])
    sahm = compute_sahm_gap(unrate)
    assert round(float(sahm.iloc[-1]), 4) == 0.4

