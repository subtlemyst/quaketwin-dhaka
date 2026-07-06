from __future__ import annotations

from quaketwin.config import BoundingBox
from quaketwin.geo.grid import make_hazard_grid
from quaketwin.hazard.amplification import apply_soil_amplification
from quaketwin.hazard.ground_motion import compute_ground_motion_grid
from quaketwin.hazard.liquefaction import compute_liquefaction_index
from quaketwin.hazard.scenario import EarthquakeScenario, load_default_scenario


def run_phase1_hazard(
    scenario: EarthquakeScenario | None = None,
    bbox: BoundingBox | None = None,
    cell_size_deg: float = 0.0045,
) -> dict:
    """
    Phase 1 pipeline: scenario → shaking → amplification → liquefaction.

    Returns a GeoJSON-ready feature collection for thesis maps and API export.
    """
    scenario = scenario or load_default_scenario()
    bbox = bbox or scenario.bbox

    grid = make_hazard_grid(bbox, cell_size_deg=cell_size_deg)
    shaking = compute_ground_motion_grid(grid, scenario)
    amplified = apply_soil_amplification(shaking)
    liquefaction = compute_liquefaction_index(amplified)

    features = []
    for row in liquefaction:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row["lon"], row["lat"]],
                },
                "properties": {
                    "scenario_id": scenario.id,
                    "pga_g": round(row["pga_g"], 4),
                    "mmi": round(row["mmi"], 2),
                    "amplified_pga_g": round(row["amplified_pga_g"], 4),
                    "amplification_factor": row.get("amplification_factor"),
                    "vs30": row.get("vs30"),
                    "soil_zone_code": row["soil_zone_code"],
                    "liquefaction_index": round(row["liquefaction_index"], 3),
                    "magnitude": scenario.magnitude,
                    "fault": scenario.fault_name,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "name": f"quaketwin_hazard_{scenario.id}",
        "metadata": {
            "phase": "1",
            "scenario": scenario.model_dump(),
            "cell_count": len(features),
            "method_note": (
                "Logic-tree GMPE (config/hazard_gmpe.yaml) + USGS Vs30 Borcherdt amplification "
                "when data/raw/vs30/usgs_vs30_dhaka.tif is present; else proxy soil zones."
            ),
        },
        "features": features,
    }
