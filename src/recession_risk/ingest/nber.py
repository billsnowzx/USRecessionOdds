from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_chronology(path: str | Path) -> pd.DataFrame:
    chronology = pd.read_csv(path, parse_dates=["peak_month", "trough_month"])
    chronology = chronology.sort_values("peak_month").reset_index(drop=True)
    return chronology


def build_monthly_recession_series(
    chronology: pd.DataFrame,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> pd.Series:
    start_ts = pd.Timestamp(start).to_period("M").to_timestamp()
    end_ts = pd.Timestamp(end).to_period("M").to_timestamp()
    index = pd.date_range(start=start_ts, end=end_ts, freq="MS")
    recession = pd.Series(0, index=index, dtype="int64", name="current_recession")

    for row in chronology.itertuples(index=False):
        recession_start = (pd.Timestamp(row.peak_month) + pd.offsets.MonthBegin(1)).to_period("M").to_timestamp()
        recession_end = pd.Timestamp(row.trough_month).to_period("M").to_timestamp()
        if recession_end < start_ts or recession_start > end_ts:
            continue
        recession.loc[max(recession_start, start_ts): min(recession_end, end_ts)] = 1

    return recession


def extract_recession_periods(recession: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if recession.empty:
        return []

    recession = recession.astype(int).sort_index()
    starts = recession[(recession == 1) & (recession.shift(fill_value=0) == 0)].index
    ends = recession[(recession == 1) & (recession.shift(-1, fill_value=0) == 0)].index
    return list(zip(starts, ends))
