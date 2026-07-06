"""Earthquake Resilience Index (ERI) — composite citywide and zonal metric."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

from quaketwin.config import ProjectSettings


def entropy_weights(component_matrix: np.ndarray) -> dict[str, float]:
    """Entropy weighting (Shannon) over zone-level component scores."""
    names = ["structural", "emergency_capacity", "lifeline_robustness", "accessibility"]
    x = np.asarray(component_matrix, dtype=float)
    x = np.clip(x, 1e-6, 1.0)
    col_sum = x.sum(axis=0, keepdims=True)
    p = x / col_sum
    n = x.shape[0]
    k = 1.0 / np.log(n)
    e = -k * (p * np.log(p)).sum(axis=0)
    d = 1.0 - e
    w = d / d.sum()
    return {names[i]: round(float(w[i]), 4) for i in range(len(names))}


def compare_eri_weighting_schemes() -> dict[str, Any]:
    """Compare manual YAML weights with entropy-derived weights."""
    root = ProjectSettings().project_root
    cfg = load_resilience_config()
    manual = cfg["weights"]

    buildings = gpd.read_file(root / "data/processed/dhaka_response_phase4.gpkg", layer="response_buildings")
    hospitals = gpd.read_file(root / "data/processed/dhaka_hospital_load_phase4.gpkg", layer="hospital_load")
    zones = gpd.read_file(root / "data/processed/cascade_zones_phase5.gpkg", layer="cascade_zones")

    cell = 0.01
    b = buildings.copy()
    b["zx"] = np.floor(b["lon"] / cell).astype(int)
    b["zy"] = np.floor(b["lat"] / cell).astype(int)
    b_agg = b.groupby(["zx", "zy"]).agg(
        mean_collapse=("collapse_probability", "mean"),
        mean_response_min=("response_time_min", "mean"),
    ).reset_index()
    parts = zones["zone_id"].str.extract(r"zone_(-?\d+)_(-?\d+)")
    zones["zx"] = parts[0].astype(int)
    zones["zy"] = parts[1].astype(int)
    z = zones.merge(b_agg, on=["zx", "zy"], how="left")
    z["mean_collapse"] = z["mean_collapse"].fillna(z["mean_collapse_p"])
    z["mean_response_min"] = z["mean_response_min"].fillna(buildings["response_time_min"].mean())

    overload = float(hospitals["overload_ratio"].clip(upper=10).mean()) / 10.0
    emerg_city = 1.0 - overload

    comp = np.column_stack([
        1.0 - z["mean_collapse"].to_numpy(),
        np.full(len(z), emerg_city),
        (1.0 - (z["expected_delay_factor"] - 1.0) / 2.0).clip(0, 1).to_numpy(),
        (1.0 / (1.0 + z["mean_response_min"] / 30.0)).to_numpy(),
    ])
    ent = entropy_weights(comp)
    std = comp.std(axis=0)
    names = ["structural", "emergency_capacity", "lifeline_robustness", "accessibility"]
    hybrid = {}
    for i, name in enumerate(names):
        hybrid[name] = ent[name] if std[i] >= 1e-6 else manual[name]
    total = sum(hybrid.values())
    hybrid = {k: round(v / total, 4) for k, v in hybrid.items()}

    def _eri(w: dict[str, float]) -> float:
        structural = 1.0 - float(buildings["collapse_probability"].mean())
        emergency = emerg_city
        lifeline = float(np.clip(1.0 - (zones["expected_delay_factor"].mean() - 1.0) / 2.0, 0, 1))
        access = 1.0 / (1.0 + float(buildings["response_time_min"].mean()) / 30.0)
        vals = [structural, emergency, lifeline, access]
        keys = ["structural", "emergency_capacity", "lifeline_robustness", "accessibility"]
        return round(100.0 * sum(w[k] * v for k, v in zip(keys, vals)), 1)

    return {
        "manual_weights": manual,
        "entropy_weights": ent,
        "entropy_hybrid_weights": hybrid,
        "citywide_eri_manual": _eri(manual),
        "citywide_eri_entropy": _eri(ent),
        "citywide_eri_entropy_hybrid": _eri(hybrid),
        "delta_points_manual_vs_hybrid": round(abs(_eri(manual) - _eri(hybrid)), 1),
    }


def load_resilience_config() -> dict[str, Any]:
    path = ProjectSettings().project_root / "config/resilience.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def compute_resilience_index(period: str = "midday") -> dict[str, Any]:
    root = ProjectSettings().project_root
    cfg = load_resilience_config()
    w = cfg["weights"]

    buildings = gpd.read_file(
        root / "data/processed/dhaka_response_phase4.gpkg",
        layer="response_buildings",
    )
    hospitals = gpd.read_file(
        root / "data/processed/dhaka_hospital_load_phase4.gpkg",
        layer="hospital_load",
    )
    zones = gpd.read_file(root / "data/processed/cascade_zones_phase5.gpkg", layer="cascade_zones")
    parts = zones["zone_id"].str.extract(r"zone_(-?\d+)_(-?\d+)")
    zones["zx"] = parts[0].astype(int)
    zones["zy"] = parts[1].astype(int)

    structural = 1.0 - float(buildings["collapse_probability"].mean())
    overload = float(hospitals["overload_ratio"].clip(upper=10).mean()) / 10.0
    emergency = 1.0 - overload
    lifeline = 1.0 - (float(zones["expected_delay_factor"].mean()) - 1.0) / 2.0
    lifeline = float(np.clip(lifeline, 0, 1))
    access = 1.0 / (1.0 + float(buildings["response_time_min"].mean()) / 30.0)

    citywide = 100.0 * (
        w["structural"] * structural
        + w["emergency_capacity"] * emergency
        + w["lifeline_robustness"] * lifeline
        + w["accessibility"] * access
    )

    # Zone-level ERI by merging cascade zones with building aggregates
    b = buildings.copy()
    cell = 0.01
    b["zx"] = np.floor(b["lon"] / cell).astype(int)
    b["zy"] = np.floor(b["lat"] / cell).astype(int)
    b_agg = b.groupby(["zx", "zy"]).agg(
        mean_collapse=("collapse_probability", "mean"),
        mean_response_min=("response_time_min", "mean"),
    ).reset_index()

    z = zones.merge(b_agg, on=["zx", "zy"], how="left")
    z["mean_collapse"] = z["mean_collapse"].fillna(z["mean_collapse_p"])
    z["mean_response_min"] = z["mean_response_min"].fillna(buildings["response_time_min"].mean())

    z_struct = 1.0 - z["mean_collapse"]
    z_life = 1.0 - (z["expected_delay_factor"] - 1.0) / 2.0
    z_life = z_life.clip(0, 1)
    z_access = 1.0 / (1.0 + z["mean_response_min"] / 30.0)
    z_emerg = emergency  # citywide proxy applied uniformly unless hospital zone data added

    z["eri_score"] = (
        100.0
        * (
            w["structural"] * z_struct
            + w["emergency_capacity"] * z_emerg
            + w["lifeline_robustness"] * z_life
            + w["accessibility"] * z_access
        )
    ).round(1)

    tiers = cfg["tiers"]
    def _tier(score: float) -> str:
        for name, (lo, hi) in tiers.items():
            if lo <= score < hi or (name == "very_high" and score >= lo):
                return name
        return "low"

    z["eri_tier"] = z["eri_score"].map(_tier)

    out_gpkg = root / "data/processed/dhaka_resilience_index.gpkg"
    z.to_file(out_gpkg, driver="GPKG", layer="resilience_zones")

    summary = {
        "period": period,
        "citywide_eri": round(citywide, 1),
        "components": {
            "structural": round(structural, 3),
            "emergency_capacity": round(emergency, 3),
            "lifeline_robustness": round(lifeline, 3),
            "accessibility": round(access, 3),
        },
        "weights": w,
        "tier_counts": z["eri_tier"].value_counts().to_dict(),
        "mean_zone_eri": round(float(z["eri_score"].mean()), 1),
        "output": str(out_gpkg),
    }
    out_json = root / "data/processed/resilience_index_summary.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return summary
