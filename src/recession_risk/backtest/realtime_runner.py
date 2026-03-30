from __future__ import annotations

from pathlib import Path

import pandas as pd

from recession_risk.backtest.metrics import summarize_predictions
from recession_risk.ingest.nber import extract_recession_periods
from recession_risk.models.logistic import SimpleLogisticRegression
from recession_risk.pipeline import build_monthly_panel


def run_realtime_backtest(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = build_monthly_panel(config, data_mode="realtime")
    runs = [
        run_realtime_logit(
            panel,
            feature_column="term_spread",
            target_name=f"within_{config['primary_horizon']}m",
            split_name="realtime_expanding",
            test_start=pd.Timestamp(config["splits"]["yield_curve"]["test_start"]),
            horizon=config["primary_horizon"],
            model_name="yield_curve_logit_realtime",
            event_mode="forecast",
            restrict_expansions=True,
        ),
        run_realtime_inversion_rule(
            panel,
            target_name=f"within_{config['primary_horizon']}m",
            test_start=pd.Timestamp(config["splits"]["yield_curve"]["test_start"]),
            horizon=config["primary_horizon"],
            threshold=float(config["thresholds"]["inversion"]),
        ),
        run_realtime_logit(
            panel,
            feature_column="BAMLH0A0HYM2",
            target_name="current_recession",
            split_name="realtime_expanding",
            test_start=pd.Timestamp(config["splits"]["hy_credit"]["test_start"]),
            horizon=0,
            model_name="hy_credit_logit_realtime",
            event_mode="detect",
            restrict_expansions=False,
        ),
        run_realtime_sahm_rule(
            panel,
            test_start=pd.Timestamp(config["splits"]["sahm"]["test_start"]),
            threshold=float(config["thresholds"]["sahm"]),
        ),
    ]

    predictions = pd.concat(runs, ignore_index=True)
    recession_periods = extract_recession_periods(panel.set_index("date")["current_recession"].astype(int))
    metrics = pd.DataFrame(
        [
            summarize_predictions(
                predictions[predictions["model_name"] == model_name],
                recession_periods,
                event_mode="forecast" if "yield_curve" in model_name else "detect",
                probability_model="logit" in model_name,
            )
            for model_name in predictions["model_name"].unique()
        ]
    )
    return predictions, metrics


def save_realtime_outputs(predictions: pd.DataFrame, metrics: pd.DataFrame, config: dict) -> tuple[Path, Path]:
    backtests_dir = config["paths"]["outputs"] / "backtests"
    backtests_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = backtests_dir / "realtime_predictions.csv"
    metrics_path = backtests_dir / "realtime_metrics.csv"
    predictions.to_csv(predictions_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    return predictions_path, metrics_path


def run_realtime_logit(
    panel: pd.DataFrame,
    feature_column: str,
    target_name: str,
    split_name: str,
    test_start: pd.Timestamp,
    horizon: int,
    model_name: str,
    event_mode: str,
    restrict_expansions: bool,
) -> pd.DataFrame:
    columns = list(dict.fromkeys(["date", "forecast_date", feature_column, target_name, "current_recession"]))
    data = panel.loc[:, columns].dropna().copy()
    if restrict_expansions:
        data = data[data["current_recession"] == 0]

    threshold = 0.5
    rows: list[dict[str, object]] = []
    test = data[data["date"] >= test_start].copy()
    for _, row in test.iterrows():
        train_cutoff = row["date"] - pd.DateOffset(months=horizon if horizon else 1)
        train = data[data["date"] <= train_cutoff].copy()
        if train.empty or train[target_name].nunique() < 2:
            continue
        model = SimpleLogisticRegression().fit(train[feature_column].to_numpy(), train[target_name].to_numpy())
        score = float(model.predict_proba([row[feature_column]])[:, 1][0])
        rows.append(
            {
                "date": row["date"],
                "forecast_date": row["forecast_date"],
                "target_name": target_name,
                "horizon": horizon,
                "model_name": model_name,
                "score": score,
                "signal": score >= threshold,
                "split_name": split_name,
                "train_end": pd.Timestamp(train["date"].max()).date().isoformat(),
                "test_start": test_start.date().isoformat(),
                "actual": row[target_name],
                "feature_value": row[feature_column],
            }
        )
    return pd.DataFrame(rows)


def run_realtime_inversion_rule(
    panel: pd.DataFrame,
    target_name: str,
    test_start: pd.Timestamp,
    horizon: int,
    threshold: float,
) -> pd.DataFrame:
    data = panel.loc[:, ["date", "forecast_date", "term_spread", "current_recession", target_name]].dropna().copy()
    data = data[(data["date"] >= test_start) & (data["current_recession"] == 0)]
    return pd.DataFrame(
        {
            "date": data["date"],
            "forecast_date": data["forecast_date"],
            "target_name": target_name,
            "horizon": horizon,
            "model_name": "yield_curve_inversion_realtime",
            "score": -data["term_spread"],
            "signal": data["term_spread"] < threshold,
            "split_name": "realtime_expanding",
            "train_end": "",
            "test_start": test_start.date().isoformat(),
            "actual": data[target_name],
            "feature_value": data["term_spread"],
        }
    )


def run_realtime_sahm_rule(panel: pd.DataFrame, test_start: pd.Timestamp, threshold: float) -> pd.DataFrame:
    data = panel.loc[:, ["date", "forecast_date", "sahm_gap", "current_recession"]].dropna().copy()
    data = data[data["date"] >= test_start]
    return pd.DataFrame(
        {
            "date": data["date"],
            "forecast_date": data["forecast_date"],
            "target_name": "current_recession",
            "horizon": 0,
            "model_name": "sahm_rule_realtime",
            "score": data["sahm_gap"],
            "signal": data["sahm_gap"] >= threshold,
            "split_name": "realtime_expanding",
            "train_end": "",
            "test_start": test_start.date().isoformat(),
            "actual": data["current_recession"],
            "feature_value": data["sahm_gap"],
        }
    )
