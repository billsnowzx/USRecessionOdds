from __future__ import annotations

import pandas as pd


def build_within_h_label(recession: pd.Series, horizon: int) -> pd.Series:
    forward_hits = pd.Series(0, index=recession.index, dtype="int64")
    for offset in range(1, horizon + 1):
        forward_hits = forward_hits | recession.shift(-offset, fill_value=0).astype(int)
    forward_hits.name = f"within_{horizon}m"
    return forward_hits.astype("int64")


def build_recession_start_series(recession: pd.Series) -> pd.Series:
    starts = ((recession == 1) & (recession.shift(fill_value=0) == 0)).astype("int64")
    starts.name = "recession_start"
    return starts
