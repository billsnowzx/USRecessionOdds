from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    merged = deepcopy(config)
    base_dir = config_path.parent.parent if config_path.parent.name == "config" else config_path.parent
    merged["_config_path"] = config_path
    merged["_base_dir"] = base_dir
    merged["paths"] = {
        name: resolve_path(base_dir, value)
        for name, value in config.get("paths", {}).items()
    }
    if "series_registry_path" in config:
        merged["series_registry_path"] = resolve_path(base_dir, config["series_registry_path"])
    return merged


def resolve_path(base_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()
