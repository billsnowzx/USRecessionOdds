from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_registry(config: dict) -> dict[str, dict[str, Any]]:
    registry = config.get("_series_registry")
    if registry is None:
        registry = load_series_registry(config["series_registry_path"])
        config["_series_registry"] = registry
    return registry


def load_series_registry(path: str | Path) -> dict[str, dict[str, Any]]:
    registry_path = Path(path)
    with registry_path.open("r", encoding="utf-8") as handle:
        registry = yaml.safe_load(handle) or {}
    return registry


def list_series_ids(config: dict) -> list[str]:
    registry = load_registry(config)
    if registry:
        return list(registry.keys())
    return list(config.get("series", {}).keys())


def list_series_specs(config: dict) -> dict[str, dict[str, Any]]:
    return {series_id: get_series_spec(config, series_id) for series_id in list_series_ids(config)}


def get_series_spec(config: dict, series_id: str) -> dict[str, Any]:
    registry = load_registry(config)

    if series_id not in registry:
        fallback = config.get("series", {}).get(series_id, {}).copy()
        fallback.setdefault("frequency", "monthly")
        fallback.setdefault("aggregation", config["aggregation"]["default"])
        fallback.setdefault("source", "FRED")
        fallback.setdefault("transform", "level")
        fallback.setdefault("realtime_eligible", False)
        return fallback

    spec = registry[series_id].copy()
    spec.setdefault("aggregation", config["aggregation"]["default"])
    spec.setdefault("release_lag_months", 0)
    spec.setdefault("release_lag_days", 0)
    spec.setdefault("source", "FRED")
    spec.setdefault("transform", "level")
    spec.setdefault("realtime_eligible", False)
    return spec
