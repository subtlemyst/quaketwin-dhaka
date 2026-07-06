"""Phase 2 validation against literature reference ranges."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np

from quaketwin.config import ProjectSettings, load_config
from quaketwin.geo.dhaka import haversine_km
from quaketwin.hazard.ground_motion import compute_ground_motion_grid
from quaketwin.hazard.scenario import load_default_scenario

# Reference PGA (g) ranges for thesis comparison — cite in Chapter 6.
# Sources: regional hazard studies for Bangladesh / Eastern Himalaya foreland;
# values are order-of-magnitude benchmarks for Mw ~7.0–7.5 at 100–200 km.
LITERATURE_BENCHMARKS = [
    {
        "id": "dhaka_150_200km_mw7",
        "description": "Bedrock PGA at 100–200 km from Mw 7.0–7.5 crustal event",
        "pga_g_min": 0.06,
        "pga_g_max": 0.25,
        "reference": "Regional GSHAP / Bangladesh seismic hazard literature (cite in thesis)",
    },
    {
        "id": "dhaka_mmi_expected",
        "description": "Expected MMI in Greater Dhaka for large eastern fault event",
        "mmi_min": 6.0,
        "mmi_max": 8.5,
        "reference": "Modified Mercalli intensity for far-field large earthquakes",
    },
]


def validate_hazard_gmpe(hazard_path: Path | None = None) -> dict[str, Any]:
    """Compare modelled PGA/MMI at Dhaka against literature benchmark ranges."""
    root = ProjectSettings().project_root
    hazard_path = hazard_path or root / "data/processed/hazard_mw72_dauki.geojson"

    with open(hazard_path, encoding="utf-8") as f:
        fc = json.load(f)

    pgas = [feat["properties"]["pga_g"] for feat in fc["features"]]
    mmis = [feat["properties"]["mmi"] for feat in fc["features"]]
    amps = [feat["properties"]["amplified_pga_g"] for feat in fc["features"]]

    scenario = load_default_scenario()
    cfg = load_config()
    center = cfg["study_area"]["center"]
    epic = cfg["faults"]["dauki"]["reference_epicenter"]
    dist_km = haversine_km(epic["lon"], epic["lat"], center["lon"], center["lat"])

    center_pga = compute_ground_motion_grid(
        [{"lon": center["lon"], "lat": center["lat"]}], scenario
    )[0]

    pga_bench = LITERATURE_BENCHMARKS[0]
    mmi_bench = LITERATURE_BENCHMARKS[1]
    mean_pga = float(np.mean(pgas))

    return {
        "scenario_id": scenario.id,
        "epicenter_to_dhaka_center_km": round(dist_km, 1),
        "model_pga_bedrock": {
            "min": round(min(pgas), 4),
            "max": round(max(pgas), 4),
            "mean": round(mean_pga, 4),
            "center": round(center_pga["pga_g"], 4),
        },
        "model_pga_amplified": {
            "min": round(min(amps), 4),
            "max": round(max(amps), 4),
            "mean": round(float(np.mean(amps)), 4),
        },
        "model_mmi": {
            "min": round(min(mmis), 2),
            "max": round(max(mmis), 2),
            "mean": round(float(np.mean(mmis)), 2),
        },
        "benchmark_checks": [
            {
                "benchmark": pga_bench["id"],
                "description": pga_bench["description"],
                "expected_range": [pga_bench["pga_g_min"], pga_bench["pga_g_max"]],
                "model_mean": round(mean_pga, 4),
                "pass": pga_bench["pga_g_min"] <= mean_pga <= pga_bench["pga_g_max"],
                "reference": pga_bench["reference"],
            },
            {
                "benchmark": mmi_bench["id"],
                "description": mmi_bench["description"],
                "expected_range": [mmi_bench["mmi_min"], mmi_bench["mmi_max"]],
                "model_mean": round(float(np.mean(mmis)), 2),
                "pass": mmi_bench["mmi_min"] <= float(np.mean(mmis)) <= mmi_bench["mmi_max"],
                "reference": mmi_bench["reference"],
            },
        ],
    }


def validate_building_risk(profiles_path: Path | None = None) -> dict[str, Any]:
    """Summary statistics for building collapse risk layer."""
    root = ProjectSettings().project_root
    profiles_path = profiles_path or root / "data/processed/dhaka_building_profiles.gpkg"
    gdf = gpd.read_file(profiles_path)

    p = gdf["collapse_probability"]
    risk_class = np.select(
        [p < 0.25, p < 0.50, p < 0.75],
        ["low", "moderate", "high"],
        default="very_high",
    )

    by_type = (
        gdf.groupby("construction_type")
        .agg(
            count=("building_id", "count"),
            mean_collapse_p=("collapse_probability", "mean"),
            mean_liquefaction=("liquefaction_index", "mean"),
            total_population=("population_est", "sum"),
        )
        .round(4)
        .sort_values("mean_collapse_p", ascending=False)
    )

    return {
        "buildings": len(gdf),
        "mean_collapse_p": round(float(p.mean()), 4),
        "median_collapse_p": round(float(p.median()), 4),
        "high_risk_count_ge_50pct": int((p >= 0.5).sum()),
        "high_risk_pct": round(float((p >= 0.5).mean()) * 100, 2),
        "total_population_est": int(gdf["population_est"].sum()),
        "risk_class_counts": {k: int(v) for k, v in pd_series_count(risk_class).items()},
        "by_construction_type": by_type.reset_index().to_dict(orient="records"),
    }


def pd_series_count(arr) -> dict:
    import pandas as pd

    return pd.Series(arr).value_counts().to_dict()
