from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

RECESSION_WINDOWS = [
    (pd.Timestamp("1990-08-01"), pd.Timestamp("1991-03-01")),
    (pd.Timestamp("2001-04-01"), pd.Timestamp("2001-11-01")),
    (pd.Timestamp("2008-01-01"), pd.Timestamp("2009-06-01")),
]


def is_recession_month(date: pd.Timestamp) -> int:
    return int(any(start <= date <= end for start, end in RECESSION_WINDOWS))


def months_until_next_recession(date: pd.Timestamp) -> int | None:
    future_starts = [start for start, _ in RECESSION_WINDOWS if start > date]
    if not future_starts:
        return None
    next_start = min(future_starts)
    return (next_start.year - date.year) * 12 + (next_start.month - date.month)


def write_synthetic_raw_data(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    months = pd.date_range("1988-01-01", "2010-12-01", freq="MS")
    daily_rows = []
    hy_rows = []
    unrate_rows = []
    payems_rows = []
    amtmno_rows = []
    cli_rows = []
    equity_rows = []
    payems_level = 100.0
    cli_level = 100.0
    equity_level = 100.0

    for date in months:
        recession = is_recession_month(date)
        months_out = months_until_next_recession(date)
        forward_signal = 0.0 if months_out is None else max(0.0, (12 - months_out) / 12)

        dgs10 = 5.0 - 0.8 * recession - 0.3 * forward_signal
        dtb3 = 3.0 + 1.4 * forward_signal + 0.4 * recession
        hy = 3.0 + 3.5 * recession + 0.8 * forward_signal
        unrate = 4.2 + 0.6 * forward_signal + 1.6 * recession
        payems_growth = 0.35 - 0.55 * recession - 0.20 * forward_signal
        cli_growth = 0.25 - 0.40 * recession - 0.15 * forward_signal
        equity_growth = 0.012 - 0.040 * recession - 0.010 * forward_signal
        amtmno = 520.0 - 90.0 * recession - 45.0 * forward_signal

        payems_level *= 1.0 + payems_growth / 100.0
        cli_level *= 1.0 + cli_growth / 100.0
        equity_level *= 1.0 + equity_growth

        daily_rows.append({"DATE": date.strftime("%Y-%m-%d"), "VALUE": round(dgs10, 4)})
        hy_rows.append({"DATE": date.strftime("%Y-%m-%d"), "VALUE": round(hy, 4)})
        daily_rows.append({"DATE": date.strftime("%Y-%m-%d"), "VALUE": round(dtb3, 4), "series": "DTB3"})
        unrate_rows.append({"DATE": date.strftime("%Y-%m-%d"), "VALUE": round(unrate, 4)})
        payems_rows.append({"DATE": date.strftime("%Y-%m-%d"), "VALUE": round(payems_level, 4)})
        amtmno_rows.append({"DATE": date.strftime("%Y-%m-%d"), "VALUE": round(amtmno, 4)})
        cli_rows.append({"DATE": date.strftime("%Y-%m-%d"), "VALUE": round(cli_level, 4)})
        equity_rows.append({"DATE": date.strftime("%Y-%m-%d"), "VALUE": round(equity_level, 4)})

    dgs10 = pd.DataFrame([row for row in daily_rows if row.get("series") is None])[["DATE", "VALUE"]]
    dtb3 = pd.DataFrame([row for row in daily_rows if row.get("series") == "DTB3"])[["DATE", "VALUE"]]
    hy = pd.DataFrame(hy_rows)
    unrate = pd.DataFrame(unrate_rows)
    payems = pd.DataFrame(payems_rows)
    amtmno = pd.DataFrame(amtmno_rows)
    cli = pd.DataFrame(cli_rows)
    equity = pd.DataFrame(equity_rows)

    dgs10.to_csv(raw_dir / "DGS10.csv", index=False)
    dtb3.to_csv(raw_dir / "DTB3.csv", index=False)
    hy.to_csv(raw_dir / "BAMLH0A0HYM2.csv", index=False)
    unrate.to_csv(raw_dir / "UNRATE.csv", index=False)
    payems.to_csv(raw_dir / "PAYEMS.csv", index=False)
    amtmno.to_csv(raw_dir / "AMTMNO.csv", index=False)
    cli.to_csv(raw_dir / "USALOLITOAASTSAM.csv", index=False)
    equity.to_csv(raw_dir / "SPASTT01USM661N.csv", index=False)


def write_reference_data(reference_dir: Path) -> None:
    reference_dir.mkdir(parents=True, exist_ok=True)
    chronology = pd.DataFrame(
        {
            "peak_month": ["1990-07-01", "2001-03-01", "2007-12-01"],
            "trough_month": ["1991-03-01", "2001-11-01", "2009-06-01"],
        }
    )
    chronology.to_csv(reference_dir / "nber_chronology.csv", index=False)


def write_test_config(base_dir: Path) -> Path:
    config = {
        "paths": {
            "raw_data": str((base_dir / "data" / "raw").as_posix()),
            "vintage_data": str((base_dir / "data" / "vintages").as_posix()),
            "processed_data": str((base_dir / "data" / "processed").as_posix()),
            "reference_data": str((base_dir / "data" / "reference").as_posix()),
            "reports": str((base_dir / "reports").as_posix()),
            "outputs": str((base_dir / "outputs").as_posix()),
        },
        "data_mode": "latest_available",
        "series_registry_path": str((base_dir / "config" / "series_registry.yaml").as_posix()),
        "realtime": {
            "use_vintages": True,
            "release_lags": True,
            "estimation_window": "expanding",
        },
        "models": {
            "multivariate": {
                "enabled": True,
                "targets": ["within_3m", "within_6m", "within_12m", "current_recession"],
                "features": ["term_spread", "DTB3", "BAMLH0A0HYM2", "sahm_gap", "UNRATE", "PAYEMS_growth_3m_ann", "AMTMNO_change_3m", "US_OECD_CLI_growth_3m", "equity_drawdown_6m"],
            },
            "regularized_logit": {
                "enabled": True,
                "targets": ["within_3m", "within_6m", "within_12m", "current_recession"],
                "features": ["term_spread", "DTB3", "BAMLH0A0HYM2", "sahm_gap", "UNRATE", "PAYEMS_growth_3m_ann", "AMTMNO_change_3m", "US_OECD_CLI_growth_3m", "equity_drawdown_6m"],
                "penalty": "elasticnet",
                "alpha": 0.1,
                "l1_ratio": 0.5,
            },
            "tree_models": {
                "enabled": False,
                "targets": ["within_3m", "within_6m", "within_12m", "current_recession"],
                "features": ["term_spread", "DTB3", "BAMLH0A0HYM2", "sahm_gap", "UNRATE", "PAYEMS_growth_3m_ann", "AMTMNO_change_3m", "US_OECD_CLI_growth_3m", "equity_drawdown_6m"],
                "n_estimators": 50,
                "learning_rate": 0.05,
                "max_depth": 2,
                "random_state": 42,
            },
            "ensemble": {
                "enabled": True,
                "members": ["yield_curve_logit", "hy_credit_logit", "multivariate_logit", "regularized_logit"],
            },
        },
        "series": {
            "DGS10": {"frequency": "daily"},
            "DTB3": {"frequency": "daily"},
            "UNRATE": {"frequency": "monthly"},
            "BAMLH0A0HYM2": {"frequency": "daily"},
            "PAYEMS": {"frequency": "monthly"},
            "AMTMNO": {"frequency": "monthly"},
            "USALOLITOAASTSAM": {"frequency": "monthly"},
            "SPASTT01USM661N": {"frequency": "monthly"},
        },
        "aggregation": {"default": "mean", "options": ["mean", "eom"]},
        "horizons": [3, 6, 12],
        "primary_horizon": 12,
        "splits": {
            "yield_curve": {"train_end": "1989-12-01", "test_start": "1990-01-01"},
            "hy_credit": {"train_end": "2006-12-01", "test_start": "2007-01-01"},
            "expanded_forecast": {"train_end": "1998-12-01", "test_start": "1999-01-01"},
            "expanded_current": {"train_end": "2006-12-01", "test_start": "2007-01-01"},
            "sahm": {"test_start": "1990-01-01"},
        },
        "thresholds": {"inversion": 0.0, "sahm": 0.5, "probability": 0.5},
        "evaluation": {
            "thresholds": [0.15, 0.25, 0.35, 0.5],
            "event_windows_months": [3, 6, 12],
            "calibration": {"enabled": True, "method": "platt", "validation_months": 24, "min_validation_months": 12},
            "minimum_history": {"min_train_months": 12, "min_positive_cases": 2, "min_negative_cases": 12},
            "selection_gates": {
                "min_auc": 0.65,
                "min_episode_recall": 0.5,
                "max_ece": 0.15,
                "max_false_alarm_streak": {
                    "current_recession": 12,
                    "within_3m": 18,
                    "within_6m": 24,
                    "within_12m": 36,
                },
            },
        },
        "reporting": {
            "include_current_snapshot": True,
            "include_event_scorecards": True,
            "include_portfolio_interpretation": True,
            "snapshot_modes": ["latest_available", "realtime"],
            "material_difference_threshold": 0.1,
            "regime_buckets": [
                {"label": "low risk", "max_probability": 0.15},
                {"label": "rising risk", "max_probability": 0.35},
                {"label": "elevated risk", "max_probability": 0.60},
                {"label": "high / imminent risk", "max_probability": 1.00},
            ],
        },
    }
    config_dir = base_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "test.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    write_series_registry(config_dir / "series_registry.yaml")
    return config_path


def write_series_registry(path: Path) -> None:
    registry = {
        "DGS10": {
            "source": "FRED",
            "frequency": "daily",
            "aggregation": "mean",
            "transform": "level",
            "realtime_eligible": True,
            "release_lag_months": 0,
            "release_lag_days": 0,
        },
        "DTB3": {
            "source": "FRED",
            "frequency": "daily",
            "aggregation": "mean",
            "transform": "level",
            "realtime_eligible": True,
            "release_lag_months": 0,
            "release_lag_days": 0,
        },
        "UNRATE": {
            "source": "FRED",
            "vintage_source": "ALFRED",
            "frequency": "monthly",
            "aggregation": "last",
            "transform": "level",
            "realtime_eligible": True,
            "release_lag_months": 1,
            "release_lag_days": 5,
        },
        "BAMLH0A0HYM2": {
            "source": "FRED",
            "frequency": "daily",
            "aggregation": "mean",
            "transform": "level",
            "realtime_eligible": True,
            "release_lag_months": 0,
            "release_lag_days": 0,
        },
        "PAYEMS": {
            "source": "FRED",
            "vintage_source": "ALFRED",
            "frequency": "monthly",
            "aggregation": "last",
            "transform": "growth_3m_annualized",
            "feature_name": "PAYEMS_growth_3m_ann",
            "realtime_eligible": True,
            "release_lag_months": 1,
            "release_lag_days": 5,
        },
        "AMTMNO": {
            "source": "FRED",
            "frequency": "monthly",
            "aggregation": "last",
            "transform": "change_3m",
            "feature_name": "AMTMNO_change_3m",
            "realtime_eligible": True,
            "release_lag_months": 1,
            "release_lag_days": 13,
        },
        "USALOLITOAASTSAM": {
            "source": "FRED",
            "vintage_source": "ALFRED",
            "frequency": "monthly",
            "aggregation": "last",
            "transform": "growth_3m",
            "feature_name": "US_OECD_CLI_growth_3m",
            "realtime_eligible": True,
            "release_lag_months": 1,
            "release_lag_days": 14,
        },
        "SPASTT01USM661N": {
            "source": "FRED",
            "frequency": "monthly",
            "aggregation": "last",
            "transform": "drawdown_6m",
            "feature_name": "equity_drawdown_6m",
            "realtime_eligible": True,
            "release_lag_months": 0,
            "release_lag_days": 0,
        },
    }
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")


def write_unrate_vintages(vintage_dir: Path) -> None:
    vintage_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "observation_date": [
                "1999-11-01",
                "1999-12-01",
                "2000-01-01",
                "2000-01-01",
                "2000-02-01",
            ],
            "vintage_date": [
                "1999-12-06",
                "2000-01-06",
                "2000-02-06",
                "2000-04-06",
                "2000-03-07",
            ],
            "value": [4.1, 4.2, 4.3, 4.9, 4.4],
        }
    )
    frame.to_csv(vintage_dir / "UNRATE.csv", index=False)
