from __future__ import annotations

from pathlib import Path

import pandas as pd

from recession_risk.backtest.event_metrics import write_evaluation_outputs
from recession_risk.backtest.metrics import summarize_predictions
from recession_risk.ingest.nber import extract_recession_periods
from recession_risk.models.ensemble import SimpleAverageEnsemble
from recession_risk.models.logit_multivariate import MultivariateLogitModel
from recession_risk.models.regularized_logit import RegularizedLogitModel
from recession_risk.models.tree_models import GradientBoostingRecessionModel


def run_expanded_models(panel: pd.DataFrame, config: dict, data_mode: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    predictions_frames: list[pd.DataFrame] = []
    metrics_rows: list[dict] = []
    summary_frames: list[pd.DataFrame] = []
    recession_periods = extract_recession_periods(panel.set_index("date")["current_recession"].astype(int))

    multivariate_cfg = config.get("models", {}).get("multivariate", {})
    if multivariate_cfg.get("enabled", False):
        for target_name in multivariate_cfg.get("targets", []):
            run_predictions, summary = run_expanding_model(
                panel=panel,
                target_name=target_name,
                feature_names=multivariate_cfg.get("features", []),
                model_name=f"multivariate_logit_{target_name}",
                model_factory=lambda features: MultivariateLogitModel(features),
                train_end=target_train_end(config, target_name),
                test_start=target_test_start(config, target_name),
            )
            if run_predictions.empty:
                continue
            predictions_frames.append(run_predictions)
            metrics_rows.append(
                summarize_predictions(
                    run_predictions,
                    recession_periods,
                    event_mode=event_mode_for_target(target_name),
                    probability_model=True,
                )
            )
            summary["model_name"] = f"multivariate_logit_{target_name}"
            summary["target_name"] = target_name
            summary["data_mode"] = data_mode
            summary_frames.append(summary)

    tree_cfg = config.get("models", {}).get("tree_models", {})
    if tree_cfg.get("enabled", False):
        for target_name in tree_cfg.get("targets", []):
            run_predictions, summary = run_expanding_model(
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
            )
            if run_predictions.empty:
                continue
            predictions_frames.append(run_predictions)
            metrics_rows.append(
                summarize_predictions(
                    run_predictions,
                    recession_periods,
                    event_mode=event_mode_for_target(target_name),
                    probability_model=True,
                )
            )
            summary["model_name"] = f"tree_boosting_{target_name}"
            summary["target_name"] = target_name
            summary["data_mode"] = data_mode
            summary_frames.append(summary)

    regularized_cfg = config.get("models", {}).get("regularized_logit", {})
    if regularized_cfg.get("enabled", False):
        for target_name in regularized_cfg.get("targets", []):
            run_predictions, summary = run_expanding_model(
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
            )
            if run_predictions.empty:
                continue
            predictions_frames.append(run_predictions)
            metrics_rows.append(
                summarize_predictions(
                    run_predictions,
                    recession_periods,
                    event_mode=event_mode_for_target(target_name),
                    probability_model=True,
                )
            )
            summary["model_name"] = f"regularized_logit_{target_name}"
            summary["target_name"] = target_name
            summary["data_mode"] = data_mode
            summary_frames.append(summary)

    ensemble_cfg = config.get("models", {}).get("ensemble", {})
    if ensemble_cfg.get("enabled", False) and predictions_frames:
        ensemble_predictions, ensemble_summaries = run_ensemble_models(
            predictions_frames,
            config,
            members=ensemble_cfg.get("members", []),
        )
        if not ensemble_predictions.empty:
            predictions_frames.append(ensemble_predictions)
            for target_name, frame in ensemble_predictions.groupby("target_name", dropna=False):
                metrics_rows.append(
                    summarize_predictions(
                        frame,
                        recession_periods,
                        event_mode=event_mode_for_target(str(target_name)),
                        probability_model=True,
                    )
                )
            if not ensemble_summaries.empty:
                ensemble_summaries["data_mode"] = data_mode
                summary_frames.append(ensemble_summaries)

    predictions = pd.concat(predictions_frames, ignore_index=True) if predictions_frames else pd.DataFrame()
    metrics = pd.DataFrame(metrics_rows)
    summaries = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    horizon = target_horizon(target_name)
    columns = list(dict.fromkeys(["date", "forecast_date", *feature_names, target_name, "current_recession"]))
    data = panel.loc[:, [column for column in columns if column in panel.columns]].dropna().copy()
    if target_name != "current_recession":
        data = data[data["current_recession"] == 0]

    train = data[data["date"] <= train_end].copy()
    test = data[data["date"] >= test_start].copy()
    split_name = "expanded_holdout"
    effective_train_end = train_end
    effective_test_start = test_start
    if train.empty or test.empty or train[target_name].nunique() < 2:
        train, test = fallback_holdout_split(data, target_name)
        split_name = "expanded_dynamic_holdout"
        if train.empty or test.empty or train[target_name].nunique() < 2:
            return pd.DataFrame(), pd.DataFrame()
        effective_train_end = pd.Timestamp(train["date"].max())
        effective_test_start = pd.Timestamp(test["date"].min())

    model = model_factory(feature_names)
    model.fit(train[feature_names].to_numpy(), train[target_name].to_numpy())
    scores = model.predict_proba(test[feature_names].to_numpy(dtype=float))[:, 1]
    predictions = pd.DataFrame(
        {
            "date": test["date"].to_numpy(),
            "forecast_date": test["forecast_date"].to_numpy() if "forecast_date" in test.columns else test["date"].to_numpy(),
            "target_name": target_name,
            "horizon": horizon,
            "model_name": model_name,
            "score": scores,
            "signal": scores >= 0.5,
            "split_name": split_name,
            "train_end": effective_train_end.date().isoformat(),
            "test_start": effective_test_start.date().isoformat(),
            "actual": test[target_name].to_numpy(),
            "feature_value": "",
            "features": ",".join(feature_names),
        }
    )
    return predictions, model.get_model_summary()


def target_horizon(target_name: str) -> int:
    if target_name.startswith("within_"):
        return int(target_name.split("_")[1].replace("m", ""))
    return 0


def target_test_start(config: dict, target_name: str) -> pd.Timestamp:
    if target_name == "current_recession":
        return pd.Timestamp(config["splits"]["hy_credit"]["test_start"])
    return pd.Timestamp(config["splits"]["yield_curve"]["test_start"])


def target_train_end(config: dict, target_name: str) -> pd.Timestamp:
    if target_name == "current_recession":
        return pd.Timestamp(config["splits"]["hy_credit"]["train_end"])
    return pd.Timestamp(config["splits"]["yield_curve"]["train_end"])


def event_mode_for_target(target_name: str) -> str:
    return "detect" if target_name == "current_recession" else "forecast"


def fallback_holdout_split(data: pd.DataFrame, target_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(data) < 10:
        return pd.DataFrame(), pd.DataFrame()
    split_index = max(int(len(data) * 0.7), 12)
    split_index = min(split_index, len(data) - 1)
    train = data.iloc[:split_index].copy()
    test = data.iloc[split_index:].copy()
    if train[target_name].nunique() < 2:
        for candidate in range(split_index + 1, len(data)):
            train = data.iloc[:candidate].copy()
            test = data.iloc[candidate:].copy()
            if train[target_name].nunique() >= 2 and not test.empty:
                break
    return train, test


def run_ensemble_models(
    prediction_frames: list[pd.DataFrame],
    config: dict,
    members: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    combined = pd.concat(prediction_frames, ignore_index=True)
    threshold = float(config["thresholds"]["probability"])
    ensemble_predictions: list[pd.DataFrame] = []
    summary_frames: list[pd.DataFrame] = []

    for target_name in sorted(combined["target_name"].dropna().unique()):
        member_frames = resolve_ensemble_members(combined, str(target_name), members)
        if len(member_frames) < 2:
            continue
        ensemble = SimpleAverageEnsemble([frame["model_name"].iloc[0] for frame in member_frames], threshold=threshold).fit(
            member_frames
        )
        merged = ensemble.predict_proba(member_frames)
        if merged.empty:
            continue
        merged["model_name"] = f"ensemble_{target_name}"
        merged["feature_value"] = ""
        merged["features"] = ",".join(ensemble.member_names)
        ensemble_predictions.append(merged)

        summary = ensemble.get_model_summary()
        summary["model_name"] = f"ensemble_{target_name}"
        summary["target_name"] = target_name
        summary_frames.append(summary)

    predictions = pd.concat(ensemble_predictions, ignore_index=True) if ensemble_predictions else pd.DataFrame()
    summaries = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    return predictions, summaries


def resolve_ensemble_members(combined: pd.DataFrame, target_name: str, members: list[str]) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for member in members:
        resolved_name = ensemble_member_model_name(member, target_name)
        if resolved_name is None:
            continue
        frame = combined[combined["model_name"] == resolved_name].sort_values("date").copy()
        if not frame.empty:
            frames.append(frame)
    return frames


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
