from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from recession_risk.models.logistic import SimpleLogisticRegression


@dataclass
class BaselineRun:
    model_name: str
    target_name: str
    horizon: int
    split_name: str
    event_mode: str
    probability_model: bool
    predictions: pd.DataFrame


def run_yield_curve_logit(panel: pd.DataFrame, config: dict, horizon: int | None = None) -> BaselineRun:
    horizon = horizon or config["primary_horizon"]
    target_name = f"within_{horizon}m"
    split = config["splits"]["yield_curve"]
    threshold = config["thresholds"]["probability"]
    train_end = pd.Timestamp(split["train_end"])
    test_start = pd.Timestamp(split["test_start"])

    data = panel.loc[:, ["date", "term_spread", "current_recession", target_name]].dropna()
    train = data[(data["date"] <= train_end) & (data["current_recession"] == 0)]
    test = data[(data["date"] >= test_start) & (data["current_recession"] == 0)]

    model = SimpleLogisticRegression().fit(train["term_spread"].to_numpy(), train[target_name].to_numpy())
    probabilities = model.predict_proba(test["term_spread"].to_numpy())[:, 1]
    predictions = _prediction_frame(
        test=test,
        model_name="yield_curve_logit",
        target_name=target_name,
        horizon=horizon,
        split_name="fixed_1990_holdout",
        train_end=train_end,
        test_start=test_start,
        score=probabilities,
        signal=probabilities >= threshold,
        feature_value=test["term_spread"].to_numpy(),
    )
    return BaselineRun("yield_curve_logit", target_name, horizon, "fixed_1990_holdout", "forecast", True, predictions)


def run_yield_curve_inversion(panel: pd.DataFrame, config: dict, horizon: int | None = None) -> BaselineRun:
    horizon = horizon or config["primary_horizon"]
    target_name = f"within_{horizon}m"
    split = config["splits"]["yield_curve"]
    train_end = pd.Timestamp(split["train_end"])
    test_start = pd.Timestamp(split["test_start"])
    threshold = config["thresholds"]["inversion"]

    test = panel.loc[:, ["date", "term_spread", "current_recession", target_name]].dropna()
    test = test[(test["date"] >= test_start) & (test["current_recession"] == 0)]
    score = -test["term_spread"].to_numpy()
    signal = test["term_spread"].to_numpy() < threshold
    predictions = _prediction_frame(
        test=test,
        model_name="yield_curve_inversion",
        target_name=target_name,
        horizon=horizon,
        split_name="fixed_1990_holdout",
        train_end=train_end,
        test_start=test_start,
        score=score,
        signal=signal,
        feature_value=test["term_spread"].to_numpy(),
    )
    return BaselineRun("yield_curve_inversion", target_name, horizon, "fixed_1990_holdout", "forecast", False, predictions)


def run_hy_credit_logit(panel: pd.DataFrame, config: dict) -> BaselineRun:
    split = config["splits"]["hy_credit"]
    threshold = config["thresholds"]["probability"]
    train_end = pd.Timestamp(split["train_end"])
    test_start = pd.Timestamp(split["test_start"])
    target_name = "current_recession"

    data = panel.loc[:, ["date", "BAMLH0A0HYM2", target_name]].dropna()
    train = data[data["date"] <= train_end]
    test = data[data["date"] >= test_start]

    model = SimpleLogisticRegression().fit(train["BAMLH0A0HYM2"].to_numpy(), train[target_name].to_numpy())
    probabilities = model.predict_proba(test["BAMLH0A0HYM2"].to_numpy())[:, 1]
    predictions = _prediction_frame(
        test=test,
        model_name="hy_credit_logit",
        target_name=target_name,
        horizon=0,
        split_name="fixed_2007_holdout",
        train_end=train_end,
        test_start=test_start,
        score=probabilities,
        signal=probabilities >= threshold,
        feature_value=test["BAMLH0A0HYM2"].to_numpy(),
    )
    return BaselineRun("hy_credit_logit", target_name, 0, "fixed_2007_holdout", "detect", True, predictions)


def run_sahm_rule(panel: pd.DataFrame, config: dict) -> BaselineRun:
    split = config["splits"]["sahm"]
    threshold = config["thresholds"]["sahm"]
    test_start = pd.Timestamp(split["test_start"])
    target_name = "current_recession"

    test = panel.loc[:, ["date", "sahm_gap", target_name]].dropna()
    test = test[test["date"] >= test_start]
    score = test["sahm_gap"].to_numpy()
    signal = score >= threshold
    predictions = _prediction_frame(
        test=test,
        model_name="sahm_rule",
        target_name=target_name,
        horizon=0,
        split_name="post_1990_monitoring",
        train_end=None,
        test_start=test_start,
        score=score,
        signal=signal,
        feature_value=score,
    )
    return BaselineRun("sahm_rule", target_name, 0, "post_1990_monitoring", "detect", False, predictions)


def _prediction_frame(
    test: pd.DataFrame,
    model_name: str,
    target_name: str,
    horizon: int,
    split_name: str,
    train_end: pd.Timestamp | None,
    test_start: pd.Timestamp,
    score,
    signal,
    feature_value,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": test["date"].to_numpy(),
            "target_name": target_name,
            "horizon": horizon,
            "model_name": model_name,
            "score": score,
            "signal": pd.Series(signal).astype(bool).to_numpy(),
            "split_name": split_name,
            "train_end": format_optional_timestamp(train_end),
            "test_start": test_start.date().isoformat(),
            "actual": test[target_name].to_numpy(),
            "feature_value": feature_value,
        }
    )


def format_optional_timestamp(value: pd.Timestamp | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()