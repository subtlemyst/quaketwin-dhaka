"""External validation against literature, analog events, and ShakeMap-style benchmarks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from quaketwin.config import ProjectSettings, load_config
from quaketwin.geo.dhaka import haversine_km
from quaketwin.hazard.ground_motion import pga_logic_tree, pga_to_mmi
from quaketwin.hazard.scenario import EarthquakeScenario

# Published/intensity-report benchmarks (order-of-magnitude external checks).
# 1897 Great Assam earthquake: Mw ~8.1, severe damage in Shillong plateau;
# Dhaka reported strong shaking — cite Oldham (1899), Ambraseys & Douglas (2004).
_ANALOG_EVENTS = [
    {
        "id": "assam_1897_analog",
        "name": "1897 Great Assam earthquake (analog)",
        "magnitude": 8.1,
        "epicenter_lon": 91.0,
        "epicenter_lat": 26.0,
        "depth_km": 15,
        "literature_mmi_dhaka": 7.0,
        "literature_mmi_range": [6.5, 7.5],
        "reference": "Oldham (1899); Ambraseys & Douglas (2004) intensity catalog",
    },
]

# Regional GMPE validation points (GSHAP / CDMP-style envelopes at distance).
_SHAKEMAP_STYLE_BENCHMARKS = [
    {"distance_km": 100, "mw": 7.2, "pga_g_range": [0.08, 0.20], "source": "GSHAP South Asia envelope"},
    {"distance_km": 150, "mw": 7.2, "pga_g_range": [0.06, 0.18], "source": "CDMP Dhaka scenario class"},
    {"distance_km": 200, "mw": 7.2, "pga_g_range": [0.04, 0.12], "source": "Regional attenuation synthesis"},
]


def _scenario_at_distance(mw: float, dist_km: float, depth_km: float = 15.0) -> dict[str, float]:
    lt = pga_logic_tree(mw, dist_km, depth_km)
    return {
        "pga_g": round(lt["pga_g"], 4),
        "mmi": round(pga_to_mmi(lt["pga_g"]), 2),
        "pga_spread_g": round(lt["pga_spread_g"], 4),
    }


def run_external_validation() -> dict[str, Any]:
    root = ProjectSettings().project_root
    cfg = load_config()
    center = cfg["study_area"]["center"]
    epic_dauki = cfg["faults"]["dauki"]["reference_epicenter"]

    dist_dauki = haversine_km(epic_dauki["lon"], epic_dauki["lat"], center["lon"], center["lat"])
    ref = _scenario_at_distance(7.2, dist_dauki)

    shakemap_checks = []
    for bench in _SHAKEMAP_STYLE_BENCHMARKS:
        model = _scenario_at_distance(bench["mw"], bench["distance_km"])
        lo, hi = bench["pga_g_range"]
        shakemap_checks.append({
            **bench,
            "model_pga_g": model["pga_g"],
            "model_mmi": model["mmi"],
            "within_envelope": lo <= model["pga_g"] <= hi,
        })

    analog_replays = []
    for ev in _ANALOG_EVENTS:
        dist = haversine_km(ev["epicenter_lon"], ev["epicenter_lat"], center["lon"], center["lat"])
        model = _scenario_at_distance(ev["magnitude"], dist, ev["depth_km"])
        lo, hi = ev["literature_mmi_range"]
        analog_replays.append({
            "event_id": ev["id"],
            "name": ev["name"],
            "distance_km": round(dist, 1),
            "model_mmi": model["mmi"],
            "literature_mmi_dhaka": ev["literature_mmi_dhaka"],
            "literature_mmi_range": ev["literature_mmi_range"],
            "mmi_within_range": lo <= model["mmi"] <= hi,
            "model_pga_g": model["pga_g"],
            "reference": ev["reference"],
            "note": (
                "Historical intensity replay uses the same GMPE logic-tree; "
                "not a full damage validation — compares order-of-magnitude shaking only."
            ),
        })

    # Load processed hazard for grid-level comparison
    hazard_path = root / "data/processed/hazard_mw72_dauki.geojson"
    grid_stats = {}
    if hazard_path.exists():
        with open(hazard_path, encoding="utf-8") as f:
            fc = json.load(f)
        amps = [feat["properties"]["amplified_pga_g"] for feat in fc["features"]]
        grid_stats = {
            "amplified_pga_mean": round(float(np.mean(amps)), 4),
            "amplified_pga_std": round(float(np.std(amps)), 4),
        }

    out = {
        "reference_scenario": {
            "id": "dhaka_mw72_dauki",
            "distance_km": round(dist_dauki, 1),
            **ref,
            **grid_stats,
        },
        "shakemap_style_distance_envelopes": shakemap_checks,
        "historical_analog_replays": analog_replays,
        "limitations": [
            "No USGS ShakeMap raster available for Bangladesh reference events in open pipeline.",
            "Hospital disruption and utility outage validation require DGHS/DPDC operational data.",
            "Building damage validation requires post-event survey or remote-sensing labels.",
        ],
    }
    path = root / "outputs/external_validation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out
