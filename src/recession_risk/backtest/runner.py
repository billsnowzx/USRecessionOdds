from __future__ import annotations

from pathlib import Path

import pandas as pd

from recession_risk.backtest.metrics import summarize_predictions
from recession_risk.ingest.nber import extract_recession_periods
from recession_risk.models.baselines import (
    BaselineRun,
    run_hy_credit_logit,
    run_sahm_rule,
    run_yield_curve_inversion,
    run_yield_curve_logit,
)
from recession_risk.models.logistic import SimpleLogisticRegression
from recession_risk.pipeline import build_monthly_panel


def run_baseline_backtests(panel: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    runs: list[BaselineRun] = [
        run_yield_curve_logit(panel, config),
        run_yield_curve_inversion(panel, config),
        run_hy_credit_logit(panel, config),
        run_sahm_rule(panel, config),
    ]
    return _summarize_runs(runs, panel)


def save_baseline_outputs(predictions: pd.DataFrame, metrics: pd.DataFrame, config: dict) -> tuple[Path, Path]:
    tables_dir = config["paths"]["reports"] / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = tables_dir / "baseline_predictions.csv"
    metrics_path = tables_dir / "baseline_metrics.csv"
    predictions.to_csv(predictions_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    return predictions_path, metrics_path


def run_robustness_backtests(config: dict) -> pd.DataFrame:
    rows: list[dict] = []

    for horizon in config["horizons"]:
        panel = build_monthly_panel(config, aggregation=config["aggregation"]["default"])
        for run in (
            run_yield_curve_logit(panel, config, horizon=horizon),
            run_yield_curve_inversion(panel, config, horizon=horizon),
        ):
            _, metrics = _summarize_runs([run], panel)
            row = metrics.iloc[0].to_dict()
            row["experiment"] = "horizon_sweep"
            rows.append(row)

    for aggregation_method in config["aggregation"]["options"]:
        panel = build_monthly_panel(config, aggregation=aggregation_method)
        _, metrics = run_baseline_backtests(panel, config)
        for row in metrics.to_dict(orient="records"):
            row["experiment"] = f"aggregation_{aggregation_method}"
            rows.append(row)

    default_panel = build_monthly_panel(config, aggregation=config["aggregation"]["default"])
    for run in (
        run_expanding_window_logit(
            default_panel,
            feature_column="term_spread",
            target_name=f"within_{config['primary_horizon']}m",
            train_end=pd.Timestamp(config["splits"]["yield_curve"]["train_end"]),
            test_start=pd.Timestamp(config["splits"]["yield_curve"]["test_start"]),
            model_name="yield_curve_logit_expanding",
            split_name="expanding_1990_holdout",
            restrict_expansions=True,
            horizon=config["primary_horizon"],
            event_mode="forecast",
        ),
        run_expanding_window_logit(
            default_panel,
            feature_column="BAMLH0A0HYM2",
            target_name="current_recession",
            train_end=pd.Timestamp(config["splits"]["hy_credit"]["train_end"]),
            test_start=pd.Timestamp(config["splits"]["hy_credit"]["test_start"]),
            model_name="hy_credit_logit_expanding",
            split_name="expanding_2007_holdout",
            restrict_expansions=False,
            horizon=0,
            event_mode="detect",
        ),
    ):
        _, metrics = _summarize_runs([run], default_panel)
        row = metrics.iloc[0].to_dict()
        row["experiment"] = "expanding_window"
        rows.append(row)

    predictions, _ = run_baseline_backtests(default_panel, config)
    recession_periods = extract_recession_periods(default_panel.set_index("date")["current_recession"].astype(int))
    periods = (
        ("pre_2008", pd.Timestamp("1990-01-01"), pd.Timestamp("2007-12-01")),
        ("post_2008", pd.Timestamp("2008-01-01"), predictions["date"].max()),
    )
    for period_name, start, end in periods:
        subset = predictions[(predictions["date"] >= start) & (predictions["date"] <= end)]
        for model_name, frame in subset.groupby("model_name"):
            row = summarize_predictions(
                frame,
                recession_periods,
                event_mode="forecast" if "yield_curve" in model_name else "detect",
                probability_model="logit" in model_name,
            )
            row["experiment"] = f"subperiod_{period_name}"
            rows.append(row)

    robustness = pd.DataFrame(rows).sort_values(["experiment", "model_name", "horizon"]).reset_index(drop=True)
    tables_dir = config["paths"]["reports"] / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    robustness.to_csv(tables_dir / "robustness_metrics.csv", index=False)
    return robustness


def run_expanding_window_logit(
    panel: pd.DataFrame,
    feature_column: str,
    target_name: str,
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    model_name: str,
    split_name: str,
    restrict_expansions: bool,
    horizon: int,
    event_mode: str,
) -> BaselineRun:
    columns = list(dict.fromkeys(["date", feature_column, target_name, "current_recession"]))
    data = panel.loc[:, columns].dropna().copy()
    if restrict_expansions:
        data = data[data["current_recession"] == 0]

    train = data[data["date"] <= train_end].copy()
    test = data[data["date"] >= test_start].copy()
    scores: list[float] = []
    for _, row in test.iterrows():
        model = SimpleLogisticRegression().fit(train[feature_column].to_numpy(), train[target_name].to_numpy())
        score = float(model.predict_proba([row[feature_column]])[:, 1][0])
        scores.append(score)
        train = pd.concat([train, row.to_frame().T], ignore_index=True)

    predictions = pd.DataFrame(
        {
            "date": test["date"].to_numpy(),
            "target_name": target_name,
            "horizon": horizon,
            "model_name": model_name,
            "score": scores,
            "signal": pd.Series(scores) >= 0.5,
            "split_name": split_name,
            "train_end": train_end.date().isoformat(),
            "test_start": test_start.date().isoformat(),
            "actual": test[target_name].to_numpy(),
            "feature_value": test[feature_column].to_numpy(),
        }
    )
    return BaselineRun(model_name, target_name, horizon, split_name, event_mode, True, predictions)


def _summarize_runs(runs: list[BaselineRun], panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    recession_periods = extract_recession_periods(panel.set_index("date")["current_recession"].astype(int))
    predictions = pd.concat([run.predictions for run in runs], ignore_index=True)
    metrics = pd.DataFrame(
        [
            summarize_predictions(run.predictions, recession_periods, run.event_mode, run.probability_model)
            for run in runs
        ]
    )
    return predictions, metrics