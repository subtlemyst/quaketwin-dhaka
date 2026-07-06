"""QuakeTwin Dhaka REST API — Phase 0–1 endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from quaketwin.config import get_bbox, load_config
from quaketwin.geo.dhaka import study_area_summary
from quaketwin.data import inventory_summary
from quaketwin.hazard.scenario import EarthquakeScenario, load_default_scenario, scenario_from_fault
from quaketwin.pipeline import run_phase1_hazard

app = FastAPI(
    title="QuakeTwin Dhaka API",
    description="Phase 0–1 thesis scaffold: data inventory, scenarios, hazard layers",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScenarioRequest(BaseModel):
    id: str = "custom_scenario"
    magnitude: float = Field(..., ge=4.0, le=9.0)
    epicenter_lon: float
    epicenter_lat: float
    depth_km: float = Field(15.0, ge=1.0, le=300.0)
    fault_name: str | None = None
    time_of_day: str = "12:00"
    season: str = "dry"


@app.get("/")
def root():
    return {
        "project": "QuakeTwin Dhaka",
        "phase": "0–5",
        "docs": "/docs",
        "endpoints": [
            "/study-area",
            "/data-inventory",
            "/scenarios/default",
            "/hazard/run",
            "/hazard/layers/{layer}",
            "/buildings/summary",
            "/exposure/diurnal",
            "/response/summary",
            "/cascade/summary",
        ],
    }


@app.get("/study-area")
def study_area():
    return study_area_summary()


@app.get("/data-inventory")
def data_inventory():
    """Phase 0: catalog of planned and acquired datasets for thesis methodology."""
    return inventory_summary()


@app.get("/scenarios/default")
def default_scenario():
    return load_default_scenario().model_dump()


@app.get("/scenarios/fault/{fault_key}")
def fault_scenario(
    fault_key: str,
    magnitude: float = Query(7.2, ge=4.0, le=9.0),
):
    cfg = load_config()
    if fault_key not in cfg["faults"]:
        raise HTTPException(404, f"Unknown fault: {fault_key}")
    return scenario_from_fault(fault_key, magnitude).model_dump()


@app.post("/hazard/run")
def hazard_run(body: ScenarioRequest | None = None):
    """Run full Phase 1 pipeline and return GeoJSON FeatureCollection."""
    scenario = (
        EarthquakeScenario(
            id=body.id,
            magnitude=body.magnitude,
            epicenter_lon=body.epicenter_lon,
            epicenter_lat=body.epicenter_lat,
            depth_km=body.depth_km,
            fault_name=body.fault_name,
            time_of_day=body.time_of_day,
            season=body.season,
        )
        if body
        else load_default_scenario()
    )
    return run_phase1_hazard(scenario=scenario)


@app.get("/hazard/layers/{layer}")
def hazard_layer(
    layer: str,
    magnitude: float = Query(7.2, ge=4.0, le=9.0),
    fault: str = Query("dauki"),
):
    """
    Export a single hazard layer as GeoJSON.

    Layers: shaking (pga/mmi), amplification, liquefaction
    """
    valid = {"shaking", "amplification", "liquefaction"}
    if layer not in valid:
        raise HTTPException(400, f"layer must be one of {sorted(valid)}")

    scenario = scenario_from_fault(fault, magnitude)
    fc = run_phase1_hazard(scenario=scenario)

    prop_map = {
        "shaking": ["pga_g", "mmi", "magnitude", "fault"],
        "amplification": ["pga_g", "amplified_pga_g", "soil_zone_code", "magnitude"],
        "liquefaction": ["liquefaction_index", "soil_zone_code", "amplified_pga_g"],
    }
    keep = set(prop_map[layer])

    features = []
    for feat in fc["features"]:
        props = {k: v for k, v in feat["properties"].items() if k in keep}
        features.append({"type": "Feature", "geometry": feat["geometry"], "properties": props})

    return {
        "type": "FeatureCollection",
        "layer": layer,
        "scenario_id": scenario.id,
        "features": features,
    }


@app.get("/health")
def health():
    return {"status": "ok", "bbox": get_bbox().model_dump()}


@app.get("/buildings/summary")
def buildings_summary():
    """Phase 2: aggregate collapse risk stats from enriched building profiles."""
    profiles = ROOT / "data/processed/dhaka_building_profiles.gpkg"
    scored = ROOT / "data/processed/dhaka_building_profiles_scored.gpkg"
    path = scored if scored.exists() else profiles
    if not path.exists():
        raise HTTPException(
            404,
            "Building profiles not found. Run scripts/build_building_profiles.py first.",
        )
    try:
        import geopandas as gpd
    except ImportError as e:
        raise HTTPException(500, "geopandas required: pip install -e '.[phase2]'") from e

    gdf = gpd.read_file(path, columns=["collapse_probability", "construction_type", "population_est"])
    return {
        "source": path.name,
        "buildings": len(gdf),
        "mean_collapse_p": round(float(gdf["collapse_probability"].mean()), 4),
        "high_risk_count": int((gdf["collapse_probability"] >= 0.5).sum()),
        "high_risk_pct": round(float((gdf["collapse_probability"] >= 0.5).mean()) * 100, 2),
        "total_population_est": int(gdf["population_est"].sum()),
        "by_construction": (
            gdf.groupby("construction_type")["collapse_probability"]
            .mean()
            .round(4)
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
        ),
    }


@app.get("/exposure/diurnal")
def diurnal_exposure():
    """Phase 3: time-of-day population and casualty exposure summary."""
    summary_path = ROOT / "data/processed/diurnal_exposure_summary.json"
    if not summary_path.exists():
        raise HTTPException(
            404,
            "Diurnal exposure not found. Run scripts/run_diurnal_exposure.py first.",
        )
    import json

    return json.loads(summary_path.read_text(encoding="utf-8"))


@app.get("/response/summary")
def response_summary():
    """Phase 4: hospital overload and rescue-priority summary."""
    import json

    summary_path = ROOT / "data/processed/response_phase4_summary.json"
    if not summary_path.exists():
        raise HTTPException(
            404,
            "Response summary not found. Run scripts/run_response_model.py first.",
        )
    return json.loads(summary_path.read_text(encoding="utf-8"))


@app.get("/cascade/summary")
def cascade_summary():
    """Phase 5: infrastructure cascade failure probabilities and rescue-delay impact."""
    import json

    summary_path = ROOT / "data/processed/cascade_phase5_summary.json"
    if not summary_path.exists():
        raise HTTPException(
            404,
            "Cascade summary not found. Run scripts/run_cascade.py first.",
        )
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    for extra in ("cascade_gnn_metrics.json", "cascade_gnn_ensemble_metrics.json"):
        metrics_path = ROOT / "data/models" / extra
        if metrics_path.exists():
            key = extra.replace(".json", "").replace("cascade_", "")
            payload[key] = json.loads(metrics_path.read_text(encoding="utf-8"))
    manifest = ROOT / "data/processed/cascade_ensemble_manifest.json"
    if manifest.exists():
        payload["ensemble"] = json.loads(manifest.read_text(encoding="utf-8"))
    return payload


@app.get("/resilience/summary")
def resilience_summary():
    """Composite Earthquake Resilience Index (ERI)."""
    import json

    path = ROOT / "data/processed/resilience_index_summary.json"
    if not path.exists():
        raise HTTPException(404, "Run scripts/run_resilience_index.py first.")
    return json.loads(path.read_text(encoding="utf-8"))
