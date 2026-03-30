from __future__ import annotations

import pandas as pd

from recession_risk.features.labels import build_recession_start_series, build_within_h_label
from recession_risk.ingest.nber import build_monthly_recession_series, extract_recession_periods


def test_build_monthly_recession_series_uses_month_after_peak():
    chronology = pd.DataFrame(
        {
            "peak_month": [pd.Timestamp("2001-03-01")],
            "trough_month": [pd.Timestamp("2001-11-01")],
        }
    )
    recession = build_monthly_recession_series(chronology, "2001-01-01", "2001-12-01")
    assert recession.loc[pd.Timestamp("2001-03-01")] == 0
    assert recession.loc[pd.Timestamp("2001-04-01")] == 1
    assert recession.loc[pd.Timestamp("2001-11-01")] == 1
    assert recession.loc[pd.Timestamp("2001-12-01")] == 0


def test_within_h_label_has_expected_alignment():
    index = pd.date_range("2000-01-01", periods=6, freq="MS")
    recession = pd.Series([0, 0, 0, 1, 1, 0], index=index)
    within_2 = build_within_h_label(recession, 2)
    assert within_2.tolist() == [0, 1, 1, 1, 0, 0]


def test_recession_starts_and_periods_are_extracted():
    index = pd.date_range("2000-01-01", periods=8, freq="MS")
    recession = pd.Series([0, 1, 1, 0, 0, 1, 1, 0], index=index)
    starts = build_recession_start_series(recession)
    periods = extract_recession_periods(recession)
    assert starts.tolist() == [0, 1, 0, 0, 0, 1, 0, 0]
    assert periods == [
        (pd.Timestamp("2000-02-01"), pd.Timestamp("2000-03-01")),
        (pd.Timestamp("2000-06-01"), pd.Timestamp("2000-07-01")),
    ]
