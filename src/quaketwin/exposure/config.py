"""Diurnal exposure configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from quaketwin.config import ProjectSettings


@lru_cache
def load_diurnal_config(path: Path | None = None) -> dict[str, Any]:
    root = ProjectSettings().project_root
    cfg_path = path or root / "config" / "diurnal_exposure.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def period_keys(config: dict | None = None) -> list[str]:
    cfg = config or load_diurnal_config()
    return list(cfg["diurnal_periods"].keys())
