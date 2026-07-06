from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from quaketwin.config import BoundingBox, get_bbox, load_config


class EarthquakeScenario(BaseModel):
    """User-specifiable earthquake scenario for hazard simulation."""

    id: str = Field(..., description="Unique scenario identifier")
    magnitude: float = Field(..., ge=4.0, le=9.0)
    magnitude_type: Literal["Mw", "Ms", "ML"] = "Mw"
    epicenter_lon: float
    epicenter_lat: float
    depth_km: float = Field(..., ge=1.0, le=300.0)
    fault_name: str | None = None
    mechanism: Literal["strike-slip", "reverse", "normal", "oblique"] = "reverse"
    time_of_day: str = "12:00"
    season: str = "dry"
    notes: str | None = None

    @property
    def epicenter(self) -> tuple[float, float]:
        return (self.epicenter_lon, self.epicenter_lat)

    @property
    def bbox(self) -> BoundingBox:
        return get_bbox()


def load_default_scenario(config: dict | None = None) -> EarthquakeScenario:
    cfg = config or load_config()
    s = cfg["default_scenario"]
    fault_key = s["fault"]
    fault = cfg["faults"][fault_key]
    return EarthquakeScenario(
        id=s["id"],
        magnitude=s["magnitude"],
        magnitude_type=s.get("magnitude_type", "Mw"),
        epicenter_lon=s["epicenter"]["lon"],
        epicenter_lat=s["epicenter"]["lat"],
        depth_km=s.get("depth_km", fault["typical_depth_km"]),
        fault_name=fault["name"],
        mechanism=s.get("mechanism", "reverse"),
        time_of_day=s.get("time_of_day", "12:00"),
        season=s.get("season", "dry"),
        notes=s.get("notes"),
    )


def scenario_from_fault(
    fault_key: str,
    magnitude: float,
    scenario_id: str | None = None,
    config: dict | None = None,
) -> EarthquakeScenario:
    cfg = config or load_config()
    fault = cfg["faults"][fault_key]
    epic = fault["reference_epicenter"]
    return EarthquakeScenario(
        id=scenario_id or f"dhaka_m{magnitude:.1f}_{fault_key}",
        magnitude=magnitude,
        epicenter_lon=epic["lon"],
        epicenter_lat=epic["lat"],
        depth_km=fault["typical_depth_km"],
        fault_name=fault["name"],
    )
