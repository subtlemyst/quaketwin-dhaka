from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from quaketwin.config import load_config


class DataSourceStatus(str, Enum):
    PLANNED = "planned"
    DOWNLOADED = "downloaded"
    PROCESSED = "processed"
    VALIDATED = "validated"


class DataSourceRecord(BaseModel):
    layer_name: str
    source_name: str
    url: str | None = None
    license: str | None = None
    status: DataSourceStatus = DataSourceStatus.PLANNED
    notes: str | None = None


def load_data_inventory(config: dict | None = None) -> list[DataSourceRecord]:
    """Phase 0 data inventory from config — export for methodology chapter."""
    cfg = config or load_config()
    records: list[DataSourceRecord] = []
    for layer, sources in cfg.get("data_sources", {}).items():
        for src in sources:
            records.append(
                DataSourceRecord(
                    layer_name=layer,
                    source_name=src["name"],
                    url=src.get("url"),
                    license=src.get("license"),
                    status=DataSourceStatus(src.get("status", "planned")),
                )
            )
    return records


def inventory_summary() -> dict:
    records = load_data_inventory()
    by_status: dict[str, int] = {}
    by_layer: dict[str, int] = {}
    for r in records:
        by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        by_layer[r.layer_name] = by_layer.get(r.layer_name, 0) + 1
    return {
        "total_sources": len(records),
        "by_status": by_status,
        "by_layer": by_layer,
        "sources": [r.model_dump() for r in records],
    }
