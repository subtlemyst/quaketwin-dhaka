from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BuildingProfile(BaseModel):
    """
    Dynamic building profile for digital twin analysis.

    Maps to `buildings` table; Phase 2 fills collapse/rescue fields via ML.
    """

    building_id: int
    lon: float
    lat: float
    construction_type: str | None = None
    height_m: float | None = None
    age_years: int | None = None
    occupancy_type: str | None = None
    population_est: int | None = None
    soil_zone_code: str | None = None
    dist_fault_km: float | None = None
    liquefaction_index: float | None = None
    dist_hospital_m: float | None = None
    road_width_m: float | None = None
    dist_open_space_m: float | None = None
    bridge_dependency: bool = False
    power_grid_dep: bool = False
    collapse_probability: float | None = Field(None, ge=0.0, le=1.0)
    fire_probability: float | None = Field(None, ge=0.0, le=1.0)
    rescue_difficulty: float | None = None
    recovery_priority: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def summary_sentence(self, scenario_mw: float) -> str:
        """Thesis-friendly per-building risk statement (Phase 2+)."""
        p_coll = self.collapse_probability
        if p_coll is None:
            return f"Building {self.building_id}: profile pending hazard overlay."
        pct = round(p_coll * 100)
        delay = self.rescue_difficulty or 0.0
        return (
            f"Building {self.building_id} has a {pct}% collapse probability "
            f"under Mw {scenario_mw:.1f}, with estimated rescue difficulty {delay:.1f}."
        )
