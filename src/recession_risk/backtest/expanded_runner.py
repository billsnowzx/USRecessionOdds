from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from recession_risk.backtest.event_metrics import write_evaluation_outputs
from recession_risk.backtest.metrics import summarize_predictions
from recession_risk.backtest.model_selection import apply_selection_gates, is_probability_model_name
from recession_risk.ingest.nber import extract_recession_periods
from recession_risk.models.calibration import PlattCalibrator
from recession_risk.models.ensemble import SimpleAverageEnsemble
from recession_risk.models.logit_multivariate import MultivariateLogitModel
from recession_risk.models.regularized_logit import RegularizedLogitModel
from recession_risk.models.tree_models import GradientBoostingRecessionModel


@dataclass
class ExpandedModelResult:
    model_name: str
    target_name: str
    predictions: pd.DataFrame
    validation_predictions: pd.DataFrame
    summary: pd.DataFrame
    status: str
    skip_reason: str = ""


def run_expanded_models(panel: pd.DataFrame, config: dict, data_mode: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    results: list[ExpandedModelResult] = []
    recession_periods = extract_recession_periods(panel.set_index("date")["current_recession"].astype(int))

    multivariate_cfg = config.get("models", {}).get("multivariate", {})
    if multivariate_cfg.get("enabled", False):
        for target_name in multivariate_cfg.get("targets", []):
            results.append(
                run_expanding_model(
                    panel=panel,
                    target_name=target_name,
                    feature_names=multivariate_cfg.get("features", []),
                    model_name=f"multivariate_logit_{target_name}",
                    model_factory=lambda features: MultivariateLogitModel(features),
                    train_end=target_train_end(config, target_name),
                    test_start=target_test_start(config, target_name),
                    config=config,
                )
            )

    tree_cfg = config.get("models", {}).get("tree_models", {})
    if tree_cfg.get("enabled", False):
        for target_name in tree_cfg.get("targets", []):
            results.append(
                run_expanding_model(
                    panel=panel,
                    target_name=target_name,
                    feature_names=tree_cfg.get("features", []),
                    model_name=f"tree_boosting_{target_name}",
                    model_factory=lambda features: GradientBoostingRecessionModel(
                        features,
                        n_estimators=int(tree_cfg.get("n_estimators", 100)),
                        learning_rate=float(tree_cfg.get("learning_rate", 0.05)),
                        max_depth=int(tree_cfg.get("max_depth", 2)),
                        random_state=int(tree_cfg.get("random_state", 42)),
                    ),
                    train_end=target_train_end(config, target_name),
                    test_start=target_test_start(config, target_name),
                    config=config,
                )
            )

    regularized_cfg = config.get("models", {}).get("regularized_logit", {})
    if regularized_cfg.get("enabled", False):
        for target_name in regularized_cfg.get("targets", []):
            results.append(
                run_expanding_model(
                    panel=panel,
                    target_name=target_name,
                    feature_names=regularized_cfg.get("features", []),
                    model_name=f"regularized_logit_{target_name}",
                    model_factory=lambda features: RegularizedLogitModel(
                        features,
                        penalty=regularized_cfg.get("penalty", "elasticnet"),
                        alpha=float(regularized_cfg.get("alpha", 0.1)),
                        l1_ratio=float(regularized_cfg.get("l1_ratio", 0.5)),
                    ),
                    train_end=target_train_end(config, target_name),
                    test_start=target_test_start(config, target_name),
                    config=config,
                )
            )

    predictions_frames = [result.predictions for result in results if not result.predictions.empty]
    metrics = summarize_results(results, recession_periods, config)

    ensemble_cfg = config.get("models", {}).get("ensemble", {})
    if ensemble_cfg.get("enabled", False) and not metrics.empty:
        ensemble_results = run_ensemble_models(
            results=results,
            metrics=metrics,
            config=config,
            members=ensemble_cfg.get("members", []),
        )
        results.extend(ensemble_results)
        predictions_frames.extend([result.predictions for result in ensemble_results if not result.predictions.empty])
        metrics = summarize_results(results, recession_periods, config)

    predictions = pd.concat(predictions_frames, ignore_index=True) if predictions_frames else pd.DataFrame()
    summaries = summarize_model_runs(results, data_mode)
    return predictions, metrics, summaries


def save_expanded_outputs(
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    summaries: pd.DataFrame,
    config: dict,
    data_mode: str,
) -> tuple[Path, Path, Path]:
    backtests_dir = config["paths"]["outputs"] / "backtests"
    backtests_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if data_mode == "latest_available" else "_realtime"
    predictions_path = backtests_dir / f"expanded_predictions{suffix}.csv"
    metrics_path = backtests_dir / f"expanded_metrics{suffix}.csv"
    summaries_path = backtests_dir / f"expanded_model_summary{suffix}.csv"
    predictions.to_csv(predictions_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    summaries.to_csv(summaries_path, index=False)
    prefix = "expanded" if data_mode == "latest_available" else "expanded_realtime"
    write_evaluation_outputs(predictions, config, prefix=prefix)
    return predictions_path, metrics_path, summaries_path


def run_expanding_model(
    panel: pd.DataFrame,
    target_name: str,
    feature_names: list[str],
    model_name: str,
    model_factory,
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    config: dict,
) -> ExpandedModelResult:
    horizon = target_horizon(target_name)
    columns = list(dict.fromkeys(["date", "forecast_date", *feature_names, target_name, "current_recession"]))
    data = panel.loc[:, [column for column in columns if column in panel.columns]].dropna().copy()
    if target_name != "current_recession":
        data = data[data["current_recession"] == 0]
    data = data.sort_values("date").reset_index(drop=True)

    train = data[data["date"] <= train_end].copy()
    test = data[data["date"] >= test_start].copy()
    skip_reason = validate_training_window(train, test, target_name, config)
    if skip_reason:
        return skipped_model_result(model_name, target_name, horizon, feature_names, skip_reason)

    model_train, calibration_window = split_train_and_validation(train, config)
    if model_train.empty:
        return skipped_model_result(model_name, target_name, horizon, feature_names, "insufficient_model_train_window")

    model = model_factory(feature_names)
    model.fit(model_train[feature_names].to_numpy(), model_train[target_name].to_numpy())
    calibrator = fit_calibrator(model, calibration_window, feature_names, target_name, config)

    validation_predictions = build_prediction_frame(
        frame=calibration_window,
        raw_scores=model.predict_proba(calibration_window[feature_names].to_numpy(dtype=float))[:, 1] if not calibration_window.empty else [],
        calibrator=calibrator,
        model_name=model_name,
        target_name=target_name,
        horizon=horizon,
        split_name="expanded_validation",
        train_end=pd.Timestamp(model_train["date"].max()) if not model_train.empty else train_end,
        test_start=pd.Timestamp(calibration_window["date"].min()) if not calibration_window.empty else test_start,
        features=feature_names,
        threshold=float(config["thresholds"]["probability"]),
    )
    predictions = build_prediction_frame(
        frame=test,
        raw_scores=model.predict_proba(test[feature_names].to_numpy(dtype=float))[:, 1],
        calibrator=calibrator,
        model_name=model_name,
        target_name=target_name,
        horizon=horizon,
        split_name="expanded_holdout",
        train_end=train_end,
        test_start=test_start,
        features=feature_names,
        threshold=float(config["thresholds"]["probability"]),
    )

    summary = pd.concat([model.get_model_summary(), calibrator.get_summary()], ignore_index=True, sort=False)
    return ExpandedModelResult(
        model_name=model_name,
        target_name=target_name,
        predictions=predictions,
        validation_predictions=validation_predictions,
        summary=summary,
        status="ok",
    )


def summarize_results(results: list[ExpandedModelResult], recession_periods: list[tuple[pd.Timestamp, pd.Timestamp]], config: dict) -> pd.DataFrame:
    metrics_rows: list[dict] = []
    for result in results:
        if result.predictions.empty:
            continue
        metrics_rows.append(
            summarize_predictions(
                result.predictions,
                recession_periods,
                event_mode=event_mode_for_target(result.target_name),
                probability_model=is_probability_model_name(result.model_name),
            )
        )
    metrics = pd.DataFrame(metrics_rows)
    if metrics.empty:
        return metrics
    return apply_selection_gates(metrics, config)


def summarize_model_runs(results: list[ExpandedModelResult], data_mode: str) -> pd.DataFrame:
    summary_frames: list[pd.DataFrame] = []
    for result in results:
        summary = result.summary.copy()
        if summary.empty:
            summary = pd.DataFrame([{"feature": "model_status", "coefficient": result.status}])
        summary["model_name"] = result.model_name
        summary["target_name"] = result.target_name
        summary["data_mode"] = data_mode
        summary["status"] = result.status
        summary["skip_reason"] = result.skip_reason
        summary_frames.append(summary)
    return pd.concat(summary_frames, ignore_index=True, sort=False) if summary_frames else pd.DataFrame()


def run_ensemble_models(
    results: list[ExpandedModelResult],
    metrics: pd.DataFrame,
    config: dict,
    members: list[str],
) -> list[ExpandedModelResult]:
    eligible_metrics = metrics[metrics["passes_selection_gates"].fillna(False)].copy()
    by_name = {result.model_name: result for result in results if not result.predictions.empty}
    ensemble_results: list[ExpandedModelResult] = []

    for target_name in sorted(eligible_metrics["target_name"].dropna().unique()):
        member_results = resolve_ensemble_members(str(target_name), members, eligible_metrics, by_name)
        if len(member_results) < 2:
            ensemble_results.append(
                skipped_model_result(
                    f"ensemble_{target_name}",
                    str(target_name),
                    target_horizon(str(target_name)),
                    [],
                    "fewer_than_two_eligible_members",
                )
            )
            continue

        ensemble = SimpleAverageEnsemble([result.model_name for result in member_results], threshold=float(config["thresholds"]["probability"])).fit(
            [result.predictions for result in member_results]
        )
        raw_validation = ensemble.predict_proba([result.validation_predictions for result in member_results if not result.validation_predictions.empty])
        if raw_validation.empty:
            raw_validation = pd.DataFrame()
        calibrator = PlattCalibrator(enabled=bool(config.get("evaluation", {}).get("calibration", {}).get("enabled", True))).fit(
            raw_validation["score"].to_numpy(dtype=float) if not raw_validation.empty else [],
            raw_validation["actual"].to_numpy(dtype=float) if not raw_validation.empty else [],
        )

        raw_test = ensemble.predict_proba([result.predictions for result in member_results])
        if raw_test.empty:
            ensemble_results.append(
                skipped_model_result(
                    f"ensemble_{target_name}",
                    str(target_name),
                    target_horizon(str(target_name)),
                    [],
                    "no_overlapping_member_predictions",
                )
            )
            continue
        raw_test["raw_score"] = raw_test["score"].astype(float)
        raw_test["calibrated_score"] = calibrator.predict(raw_test["raw_score"].to_numpy(dtype=float))
        raw_test["score"] = raw_test["calibrated_score"]
        raw_test["signal"] = raw_test["score"] >= float(config["thresholds"]["probability"])
        raw_test["model_name"] = f"ensemble_{target_name}"
        raw_test["feature_value"] = ""
        raw_test["features"] = ",".join(ensemble.member_names)

        summary = pd.concat([ensemble.get_model_summary(), calibrator.get_summary()], ignore_index=True, sort=False)
        ensemble_results.append(
            ExpandedModelResult(
                model_name=f"ensemble_{target_name}",
                target_name=str(target_name),
                predictions=raw_test,
                validation_predictions=raw_validation,
                summary=summary,
                status="ok",
            )
        )

    return ensemble_results


def build_prediction_frame(
    frame: pd.DataFrame,
    raw_scores,
    calibrator: PlattCalibrator,
    model_name: str,
    target_name: str,
    horizon: int,
    split_name: str,
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    features: list[str],
    threshold: float = 0.5,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    prediction_frame = pd.DataFrame(
        {
            "date": frame["date"].to_numpy(),
            "forecast_date": frame["forecast_date"].to_numpy() if "forecast_date" in frame.columns else frame["date"].to_numpy(),
            "target_name": target_name,
            "horizon": horizon,
            "model_name": model_name,
            "raw_score": pd.Series(raw_scores, dtype=float).to_numpy(),
            "split_name": split_name,
            "train_end": pd.Timestamp(train_end).date().isoformat(),
            "test_start": pd.Timestamp(test_start).date().isoformat(),
            "actual": frame[target_name].to_numpy(),
            "feature_value": "",
            "features": ",".join(features),
        }
    )
    prediction_frame["calibrated_score"] = calibrator.predict(prediction_frame["raw_score"].to_numpy(dtype=float))
    prediction_frame["score"] = prediction_frame["calibrated_score"]
    prediction_frame["signal"] = prediction_frame["score"] >= threshold
    return prediction_frame


def fit_calibrator(model, calibration_window: pd.DataFrame, feature_names: list[str], target_name: str, config: dict) -> PlattCalibrator:
    enabled = bool(config.get("evaluation", {}).get("calibration", {}).get("enabled", True))
    calibrator = PlattCalibrator(enabled=enabled)
    if calibration_window.empty:
        return calibrator.fit([], [])
    raw_scores = model.predict_proba(calibration_window[feature_names].to_numpy(dtype=float))[:, 1]
    return calibrator.fit(raw_scores, calibration_window[target_name].to_numpy(dtype=float))


def split_train_and_validation(train: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    calibration_cfg = config.get("evaluation", {}).get("calibration", {})
    validation_months = int(calibration_cfg.get("validation_months", 24))
    min_validation_months = int(calibration_cfg.get("min_validation_months", 12))
    if len(train) <= max(validation_months, min_validation_months):
        return train.copy(), pd.DataFrame(columns=train.columns)
    calibration_window = train.tail(validation_months).copy()
    if len(calibration_window) < min_validation_months:
        return train.copy(), pd.DataFrame(columns=train.columns)
    model_train = train.iloc[: len(train) - len(calibration_window)].copy()
    return model_train, calibration_window


def validate_training_window(train: pd.DataFrame, test: pd.DataFrame, target_name: str, config: dict) -> str:
    if train.empty:
        return "empty_training_window"
    if test.empty:
        return "empty_test_window"

    minimum_history = config.get("evaluation", {}).get("minimum_history", {})
    min_train_months = int(minimum_history.get("min_train_months", 60))
    min_positive_cases = int(minimum_history.get("min_positive_cases", 2))
    min_negative_cases = int(minimum_history.get("min_negative_cases", 12))

    if len(train) < min_train_months:
        return f"train_months<{min_train_months}"
    positives = int(train[target_name].sum())
    negatives = int((train[target_name] == 0).sum())
    if positives < min_positive_cases:
        return f"positive_cases<{min_positive_cases}"
    if negatives < min_negative_cases:
        return f"negative_cases<{min_negative_cases}"
    if train[target_name].nunique() < 2:
        return "single_class_training_window"
    return ""


def skipped_model_result(model_name: str, target_name: str, horizon: int, feature_names: list[str], skip_reason: str) -> ExpandedModelResult:
    return ExpandedModelResult(
        model_name=model_name,
        target_name=target_name,
        predictions=pd.DataFrame(),
        validation_predictions=pd.DataFrame(),
        summary=pd.DataFrame([{"feature": "model_status", "coefficient": "skipped"}]),
        status="skipped",
        skip_reason=skip_reason,
    )


def target_horizon(target_name: str) -> int:
    if target_name.startswith("within_"):
        return int(target_name.split("_")[1].replace("m", ""))
    return 0


def target_test_start(config: dict, target_name: str) -> pd.Timestamp:
    if target_name == "current_recession":
        split_key = "expanded_current" if "expanded_current" in config.get("splits", {}) else "hy_credit"
        return pd.Timestamp(config["splits"][split_key]["test_start"])
    split_key = "expanded_forecast" if "expanded_forecast" in config.get("splits", {}) else "yield_curve"
    return pd.Timestamp(config["splits"][split_key]["test_start"])


def target_train_end(config: dict, target_name: str) -> pd.Timestamp:
    if target_name == "current_recession":
        split_key = "expanded_current" if "expanded_current" in config.get("splits", {}) else "hy_credit"
        return pd.Timestamp(config["splits"][split_key]["train_end"])
    split_key = "expanded_forecast" if "expanded_forecast" in config.get("splits", {}) else "yield_curve"
    return pd.Timestamp(config["splits"][split_key]["train_end"])


def event_mode_for_target(target_name: str) -> str:
    return "detect" if target_name == "current_recession" else "forecast"


def resolve_ensemble_members(
    target_name: str,
    members: list[str],
    eligible_metrics: pd.DataFrame,
    by_name: dict[str, ExpandedModelResult],
) -> list[ExpandedModelResult]:
    resolved_results: list[ExpandedModelResult] = []
    for member in members:
        resolved_name = ensemble_member_model_name(member, target_name)
        if resolved_name is None:
            continue
        if resolved_name not in set(eligible_metrics["model_name"]):
            continue
        result = by_name.get(resolved_name)
        if result is None:
            continue
        resolved_results.append(result)
    return resolved_results


def ensemble_member_model_name(member: str, target_name: str) -> str | None:
    if member in {"multivariate_logit", "regularized_logit", "tree_boosting"}:
        return f"{member}_{target_name}"
    if member == "yield_curve_logit" and target_name == "within_12m":
        return member
    if member == "yield_curve_inversion" and target_name == "within_12m":
        return member
    if member == "hy_credit_logit" and target_name == "current_recession":
        return member
    if member == "sahm_rule" and target_name == "current_recession":
        return member
    return None
