from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from recession_risk.ingest.nber import load_chronology


def summarize_event_metrics(
    predictions: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    event_mode: str,
    lookback_months: int | None,
) -> dict[str, float | int]:
    scorecard = build_event_scorecard(predictions, recession_periods, event_mode, lookback_months)
    false_alarm_streak = max_false_alarm_streak(predictions)
    false_positive_months = int((predictions["signal"].astype(bool) & (predictions["actual"].astype(int) == 0)).sum())

    if scorecard.empty:
        return {
            "event_hit_rate": float("nan"),
            "median_timing_months": float("nan"),
            "average_timing_months": float("nan"),
            "flagged_3m_ahead_share": float("nan"),
            "flagged_6m_ahead_share": float("nan"),
            "episode_recall": float("nan"),
            "max_false_alarm_streak": false_alarm_streak,
            "event_hits": 0,
            "n_events": 0,
            "false_positive_months": false_positive_months,
        }

    hits = int(scorecard["hit"].sum())
    timings = scorecard.loc[scorecard["hit"], "timing_months"].astype(float)

    return {
        "event_hit_rate": hits / len(scorecard),
        "median_timing_months": float(timings.median()) if not timings.empty else float("nan"),
        "average_timing_months": float(timings.mean()) if not timings.empty else float("nan"),
        "flagged_3m_ahead_share": scorecard["flagged_3m_ahead"].mean(skipna=True),
        "flagged_6m_ahead_share": scorecard["flagged_6m_ahead"].mean(skipna=True),
        "episode_recall": scorecard["hit"].mean(),
        "max_false_alarm_streak": false_alarm_streak,
        "event_hits": hits,
        "n_events": int(len(scorecard)),
        "false_positive_months": false_positive_months,
    }


def build_event_scorecard(
    predictions: pd.DataFrame,
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    event_mode: str,
    lookback_months: int | None,
) -> pd.DataFrame:
    frame = predictions.copy()
    if frame.empty:
        return pd.DataFrame(columns=_scorecard_columns())

    frame["date"] = pd.to_datetime(frame["date"])
    frame["signal"] = frame["signal"].astype(bool)
    frame["score"] = frame["score"].astype(float)
    frame = frame.sort_values("date").reset_index(drop=True)

    min_date = pd.Timestamp(frame["date"].min()).to_period("M").to_timestamp()
    max_date = pd.Timestamp(frame["date"].max()).to_period("M").to_timestamp()
    periods = eligible_recession_periods(recession_periods, min_date, max_date, event_mode)

    rows: list[dict[str, object]] = []
    previous_end: pd.Timestamp | None = None
    for episode_number, (start, end) in enumerate(periods, start=1):
        if event_mode == "forecast":
            if lookback_months is None:
                raise ValueError("Forecast event mode requires lookback_months.")
            warning_window_start = max(min_date, start - pd.DateOffset(months=lookback_months))
            warning_window = frame[(frame["date"] >= warning_window_start) & (frame["date"] < start)].copy()
            warning_signals = warning_window[warning_window["signal"]]
            first_warning = warning_signals["date"].min() if not warning_signals.empty else pd.NaT
            timing_months = month_difference(first_warning, start) if pd.notna(first_warning) else np.nan
            max_score_in_window = float(warning_window["score"].max()) if not warning_window.empty else np.nan

            false_alarm_end = start - pd.DateOffset(months=lookback_months)
            false_alarm_start = min_date if previous_end is None else previous_end + pd.offsets.MonthBegin(1)
            false_alarm_window = frame[(frame["date"] >= false_alarm_start) & (frame["date"] < false_alarm_end)].copy()
            false_alarm_signals = false_alarm_window[false_alarm_window["signal"]]
            false_alarm_months = int(len(false_alarm_signals))
            false_alarm_streak = max_consecutive_signal_months(false_alarm_window)
        else:
            warning_window = frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()
            warning_signals = warning_window[warning_window["signal"]]
            first_warning = warning_signals["date"].min() if not warning_signals.empty else pd.NaT
            timing_months = month_difference(start, first_warning) if pd.notna(first_warning) else np.nan
            max_score_in_window = float(warning_window["score"].max()) if not warning_window.empty else np.nan

            false_alarm_start = min_date if previous_end is None else previous_end + pd.offsets.MonthBegin(1)
            false_alarm_window = frame[(frame["date"] >= false_alarm_start) & (frame["date"] < start)].copy()
            false_alarm_signals = false_alarm_window[false_alarm_window["signal"]]
            false_alarm_months = int(len(false_alarm_signals))
            false_alarm_streak = max_consecutive_signal_months(false_alarm_window)

        hit = pd.notna(first_warning)
        rows.append(
            {
                "model_name": frame["model_name"].iloc[0],
                "target_name": frame["target_name"].iloc[0],
                "horizon": int(frame["horizon"].iloc[0]),
                "split_name": frame["split_name"].iloc[0],
                "event_mode": event_mode,
                "episode_number": episode_number,
                "episode_start": start.date().isoformat(),
                "episode_end": end.date().isoformat(),
                "first_warning_date": first_warning.date().isoformat() if pd.notna(first_warning) else "",
                "hit": bool(hit),
                "timing_months": float(timing_months) if pd.notna(timing_months) else np.nan,
                "timing_type": "lead" if event_mode == "forecast" else "lag",
                "flagged_3m_ahead": bool(hit and event_mode == "forecast" and float(timing_months) >= 3) if hit else False,
                "flagged_6m_ahead": bool(hit and event_mode == "forecast" and float(timing_months) >= 6) if hit else False,
                "max_score_in_window": max_score_in_window,
                "false_alarm_months_before_episode": false_alarm_months,
                "false_alarm_streak_before_episode": false_alarm_streak,
            }
        )
        previous_end = end

    return pd.DataFrame(rows, columns=_scorecard_columns())


def build_episode_summary(scorecard: pd.DataFrame) -> pd.DataFrame:
    if scorecard.empty:
        return pd.DataFrame(columns=_episode_summary_columns())

    def mean_or_nan(series: pd.Series) -> float:
        non_null = series.dropna()
        return float(non_null.mean()) if not non_null.empty else float("nan")

    rows: list[dict[str, object]] = []
    for _, frame in scorecard.groupby(["model_name", "target_name", "horizon", "split_name", "event_mode"], dropna=False):
        hits = frame[frame["hit"]]
        rows.append(
            {
                "model_name": frame["model_name"].iloc[0],
                "target_name": frame["target_name"].iloc[0],
                "horizon": int(frame["horizon"].iloc[0]),
                "split_name": frame["split_name"].iloc[0],
                "event_mode": frame["event_mode"].iloc[0],
                "episodes": int(len(frame)),
                "episode_hits": int(frame["hit"].sum()),
                "episode_recall": float(frame["hit"].mean()),
                "average_timing_months": mean_or_nan(hits["timing_months"]),
                "median_timing_months": float(hits["timing_months"].median()) if not hits.empty else float("nan"),
                "flagged_3m_ahead_share": mean_or_nan(frame["flagged_3m_ahead"].where(frame["event_mode"] == "forecast")),
                "flagged_6m_ahead_share": mean_or_nan(frame["flagged_6m_ahead"].where(frame["event_mode"] == "forecast")),
                "avg_false_alarm_months_before_episode": float(frame["false_alarm_months_before_episode"].mean()),
                "max_false_alarm_streak_before_episode": int(frame["false_alarm_streak_before_episode"].max()),
                "max_score_in_window": float(frame["max_score_in_window"].max()) if frame["max_score_in_window"].notna().any() else float("nan"),
            }
        )
    return pd.DataFrame(rows, columns=_episode_summary_columns())


def write_evaluation_outputs(predictions: pd.DataFrame, config: dict, prefix: str) -> tuple[Path, Path, Path]:
    from recession_risk.backtest.thresholds import build_threshold_analysis

    backtests_dir = config["paths"]["outputs"] / "backtests"
    backtests_dir.mkdir(parents=True, exist_ok=True)
    recession_periods = load_recession_periods_from_config(config)

    scorecards: list[pd.DataFrame] = []
    if not predictions.empty:
        for _, frame in predictions.groupby("model_name", dropna=False):
            target_name = str(frame["target_name"].iloc[0])
            event_mode = "detect" if target_name == "current_recession" else "forecast"
            lookback_months = int(frame["horizon"].iloc[0]) if event_mode == "forecast" else None
            scorecard = build_event_scorecard(frame, recession_periods, event_mode, lookback_months)
            if not scorecard.empty:
                scorecards.append(scorecard)

    event_scorecard = pd.concat(scorecards, ignore_index=True) if scorecards else pd.DataFrame(columns=_scorecard_columns())
    episode_summary = build_episode_summary(event_scorecard)
    threshold_analysis = build_threshold_analysis(predictions, recession_periods, config)

    event_scorecard_path = backtests_dir / f"{prefix}_event_scorecard.csv"
    episode_summary_path = backtests_dir / f"{prefix}_episode_summary.csv"
    threshold_analysis_path = backtests_dir / f"{prefix}_threshold_analysis.csv"

    event_scorecard.to_csv(event_scorecard_path, index=False)
    episode_summary.to_csv(episode_summary_path, index=False)
    threshold_analysis.to_csv(threshold_analysis_path, index=False)
    return event_scorecard_path, episode_summary_path, threshold_analysis_path


def load_recession_periods_from_config(config: dict) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    chronology_path = config["paths"]["reference_data"] / "nber_chronology.csv"
    chronology = load_chronology(chronology_path)
    periods: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for row in chronology.itertuples(index=False):
        start = (pd.Timestamp(row.peak_month) + pd.offsets.MonthBegin(1)).to_period("M").to_timestamp()
        end = pd.Timestamp(row.trough_month).to_period("M").to_timestamp()
        periods.append((start, end))
    return periods


def eligible_recession_periods(
    recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]],
    min_date: pd.Timestamp,
    max_date: pd.Timestamp,
    event_mode: str,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if event_mode == "forecast":
        return [(start, end) for start, end in recession_periods if min_date <= start <= max_date]
    return [(start, end) for start, end in recession_periods if not (end < min_date or start > max_date)]


def max_false_alarm_streak(predictions: pd.DataFrame) -> int:
    frame = predictions.copy()
    if frame.empty:
        return 0
    frame["signal"] = frame["signal"].astype(bool)
    frame["actual"] = frame["actual"].astype(int)
    false_alarm = frame["signal"] & (frame["actual"] == 0)
    streak = 0
    max_streak = 0
    for value in false_alarm:
        if value:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def max_consecutive_signal_months(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    streak = 0
    max_streak = 0
    for value in frame["signal"].astype(bool):
        if value:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def month_difference(start: pd.Timestamp, end: pd.Timestamp) -> int:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return (end_ts.year - start_ts.year) * 12 + (end_ts.month - start_ts.month)


def _scorecard_columns() -> list[str]:
    return [
        "model_name",
        "target_name",
        "horizon",
        "split_name",
        "event_mode",
        "episode_number",
        "episode_start",
        "episode_end",
        "first_warning_date",
        "hit",
        "timing_months",
        "timing_type",
        "flagged_3m_ahead",
        "flagged_6m_ahead",
        "max_score_in_window",
        "false_alarm_months_before_episode",
        "false_alarm_streak_before_episode",
    ]


def _episode_summary_columns() -> list[str]:
    return [
        "model_name",
        "target_name",
        "horizon",
        "split_name",
        "event_mode",
        "episodes",
        "episode_hits",
        "episode_recall",
        "average_timing_months",
        "median_timing_months",
        "flagged_3m_ahead_share",
        "flagged_6m_ahead_share",
        "avg_false_alarm_months_before_episode",
        "max_false_alarm_streak_before_episode",
        "max_score_in_window",
    ]
