from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BoundingBox(BaseModel):
    west: float
    south: float
    east: float
    north: float

    @property
    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)


class ProjectSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QUAKETWIN_")

    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2]
    )
    config_path: Path | None = None
    database_url: str = "postgresql://localhost:5432/quaketwin"


@lru_cache
def load_config(path: Path | None = None) -> dict[str, Any]:
    settings = ProjectSettings()
    config_file = path or settings.config_path or settings.project_root / "config" / "dhaka.yaml"
    with open(config_file, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_bbox(config: dict[str, Any] | None = None) -> BoundingBox:
    cfg = config or load_config()
    return BoundingBox(**cfg["study_area"]["bbox"])
