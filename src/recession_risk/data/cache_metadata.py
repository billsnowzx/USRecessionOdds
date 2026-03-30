from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_path_for(path: str | Path) -> Path:
    return Path(path).with_suffix(".metadata.json")


def write_metadata(path: str | Path, payload: dict[str, Any]) -> Path:
    destination = metadata_path_for(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    enriched = {"metadata_written_at_utc": utc_now_iso(), **payload}
    destination.write_text(json.dumps(enriched, indent=2, sort_keys=True), encoding="utf-8")
    return destination


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()
