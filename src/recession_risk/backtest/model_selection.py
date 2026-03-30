from __future__ import annotations

import math

import pandas as pd

BENCHMARK_PREFIXES = (
    "yield_curve_logit",
    "yield_curve_inversion",
    "hy_credit_logit",
    "sahm_rule",
)


def is_probability_model_name(model_name: str) -> bool:
    lowered = str(model_name).lower()
    return any(token in lowered for token in ["logit", "multivariate", "regularized", "ensemble", "tree"])


def is_benchmark_model_name(model_name: str) -> bool:
    return any(str(model_name).startswith(prefix) for prefix in BENCHMARK_PREFIXES)


def apply_selection_gates(metrics: pd.DataFrame, config: dict) -> pd.DataFrame:
    if metrics.empty:
        return metrics.copy()

    gates = config.get("evaluation", {}).get("selection_gates", {})
    enriched = metrics.copy()
    pass_flags: list[bool] = []
    reasons: list[str] = []

    for _, row in enriched.iterrows():
        threshold_reasons: list[str] = []
        target_name = str(row["target_name"])
        model_name = str(row["model_name"])

        min_auc = float(gates.get("min_auc", 0.65))
        min_recall = float(gates.get("min_episode_recall", 0.5))
        max_ece = float(gates.get("max_ece", 0.15))
        false_alarm_caps = gates.get("max_false_alarm_streak", {})
        false_alarm_cap = int(false_alarm_caps.get(target_name, 9999))

        auc = safe_float(row.get("auc"))
        if math.isnan(auc) or auc < min_auc:
            threshold_reasons.append(f"auc<{min_auc:.2f}")

        episode_recall = safe_float(row.get("episode_recall"))
        if math.isnan(episode_recall) or episode_recall < min_recall:
            threshold_reasons.append(f"episode_recall<{min_recall:.2f}")

        if is_probability_model_name(model_name):
            ece = safe_float(row.get("ece"))
            if math.isnan(ece) or ece > max_ece:
                threshold_reasons.append(f"ece>{max_ece:.2f}")

        false_alarm_streak = safe_float(row.get("max_false_alarm_streak"))
        if math.isnan(false_alarm_streak) or false_alarm_streak > false_alarm_cap:
            threshold_reasons.append(f"max_false_alarm_streak>{false_alarm_cap}")

        pass_flags.append(not threshold_reasons)
        reasons.append("; ".join(threshold_reasons))

    enriched["is_benchmark"] = enriched["model_name"].apply(is_benchmark_model_name)
    enriched["is_probability_model"] = enriched["model_name"].apply(is_probability_model_name)
    enriched["passes_selection_gates"] = pass_flags
    enriched["selection_gate_reasons"] = reasons
    return enriched


def sort_candidate_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    sortable = metrics.copy()
    for column in ["auc", "episode_recall", "precision"]:
        if column not in sortable.columns:
            sortable[column] = float("nan")
    return sortable.sort_values(
        ["passes_selection_gates", "is_probability_model", "auc", "episode_recall", "precision"],
        ascending=[False, False, False, False, False],
    )


def safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")
