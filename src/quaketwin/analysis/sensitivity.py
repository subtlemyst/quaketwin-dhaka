"""One-at-a-time sensitivity studies backing manuscript claims."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml

from quaketwin.config import ProjectSettings, load_config
from quaketwin.exposure.casualties import expected_casualties_vectorized, load_casualty_rates
from quaketwin.geo.dhaka import haversine_km
from quaketwin.hazard.ground_motion import _load_gmpe_config, _pga_single, pga_logic_tree
from quaketwin.hazard.scenario import load_default_scenario
from quaketwin.resilience.pipeline import load_resilience_config


def _root() -> Path:
    return ProjectSettings().project_root


def gmpe_weight_sensitivity() -> dict[str, Any]:
    """Vary logic-tree branch weights at Dhaka center distance."""
    scenario = load_default_scenario()
    bbox = load_config()["study_area"]["bbox"]
    center_lon = (bbox["west"] + bbox["east"]) / 2
    center_lat = (bbox["south"] + bbox["north"]) / 2
    dist = haversine_km(scenario.epicenter_lon, scenario.epicenter_lat, center_lon, center_lat)
    cfg = _load_gmpe_config()
    branches = cfg["logic_tree"]
    baseline = pga_logic_tree(scenario.magnitude, dist, scenario.depth_km)["pga_g"]

    prof = _root() / "data/processed/dhaka_building_profiles.gpkg"
    amp_baseline = None
    if prof.exists():
        b = gpd.read_file(prof, layer="building_profiles", columns=["amplified_pga_g"])
        amp_baseline = float(b["amplified_pga_g"].mean())

    splits = [(0.55, 0.45), (0.50, 0.50), (0.45, 0.55), (0.40, 0.60), (0.60, 0.40)]
    rows = []
    for w0, w1 in splits:
        pgas = [
            _pga_single(scenario.magnitude, dist, scenario.depth_km, branches[0]),
            _pga_single(scenario.magnitude, dist, scenario.depth_km, branches[1]),
        ]
        pga = (w0 * pgas[0] + w1 * pgas[1]) / (w0 + w1)
        pct = abs(pga - baseline) / max(baseline, 1e-9) * 100
        row: dict[str, Any] = {
            "w_boore": w0,
            "w_ab2006": w1,
            "bedrock_pga_g": round(pga, 4),
            "pct_change_vs_55_45": round(pct, 2),
        }
        if amp_baseline is not None:
            amp_est = amp_baseline * (pga / baseline)
            row["est_mean_amplified_pga_g"] = round(amp_est, 4)
            row["est_amplified_pct_change"] = round(abs(amp_est - amp_baseline) / amp_baseline * 100, 2)
        rows.append(row)
    max_amp_pct = max(r.get("est_amplified_pct_change", r["pct_change_vs_55_45"]) for r in rows)
    return {
        "center_distance_km": round(dist, 1),
        "baseline_pga_g": round(baseline, 4),
        "rows": rows,
        "max_amplified_pct_change": round(max_amp_pct, 2),
    }


def occupancy_multiplier_sensitivity(scale: float = 0.20, period: str = "midday") -> dict[str, Any]:
    """Perturb non-residential occupancy multipliers ±scale (residential fixed)."""
    root = _root()
    with open(root / "config/diurnal_exposure.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    mult = cfg["occupancy_multipliers"]
    rates = load_casualty_rates(cfg)

    b = gpd.read_file(root / "data/processed/dhaka_building_profiles.gpkg", layer="building_profiles")
    static_pop = float(b["population_est"].sum())
    collapse = b["collapse_probability"].to_numpy()
    occ = b["occupancy_type"].fillna("residential").astype(str) if "occupancy_type" in b.columns else pd.Series(["residential"] * len(b))
    base_mult = occ.map(lambda o: float(mult.get(o, mult["residential"]).get(period, 1.0))).to_numpy(dtype=float)

    def _casualties_for(non_res_scale: float) -> float:
        m = np.where(occ.to_numpy() != "residential", base_mult * non_res_scale, base_mult)
        raw = b["population_est"].to_numpy(dtype=float) * m
        scale_t = static_pop / max(raw.sum(), 1e-9)
        pop_t = raw * scale_t
        cas = expected_casualties_vectorized(pop_t, collapse, occ, rates)
        return float(cas.sum())

    base = _casualties_for(1.0)
    low = _casualties_for(1.0 - scale)
    high = _casualties_for(1.0 + scale)
    return {
        "period": period,
        "scale": scale,
        "note": "Non-residential occupancy multipliers scaled; residential fixed; citywide total conserved.",
        "baseline_casualties": int(round(base)),
        "low_scale_casualties": int(round(low)),
        "high_scale_casualties": int(round(high)),
        "max_pct_change": round(max(abs(low - base), abs(high - base)) / max(base, 1e-9) * 100, 2),
    }


def eri_weight_sensitivity(delta: float = 0.10) -> dict[str, Any]:
    """One-at-a-time ±delta perturbations on ERI component weights."""
    root = _root()
    cfg = load_resilience_config()
    base_w = cfg["weights"]
    buildings = gpd.read_file(root / "data/processed/dhaka_response_phase4.gpkg", layer="response_buildings")
    hospitals = gpd.read_file(root / "data/processed/dhaka_hospital_load_phase4.gpkg", layer="hospital_load")
    zones = gpd.read_file(root / "data/processed/cascade_zones_phase5.gpkg", layer="cascade_zones")

    structural = 1.0 - float(buildings["collapse_probability"].mean())
    emergency = 1.0 - float(hospitals["overload_ratio"].clip(upper=10).mean()) / 10.0
    lifeline = float(np.clip(1.0 - (float(zones["expected_delay_factor"].mean()) - 1.0) / 2.0, 0, 1))
    access = 1.0 / (1.0 + float(buildings["response_time_min"].mean()) / 30.0)
    comps = {
        "structural": structural,
        "emergency_capacity": emergency,
        "lifeline_robustness": lifeline,
        "accessibility": access,
    }

    def _eri(w: dict[str, float]) -> float:
        s = sum(w.values())
        wn = {k: v / s for k, v in w.items()}
        return 100.0 * sum(wn[k] * comps[k] for k in comps)

    baseline = _eri(base_w)
    rows = []
    for key in base_w:
        for sign, label in [(1, "+"), (-1, "-")]:
            w = copy.deepcopy(base_w)
            w[key] = max(0.05, w[key] + sign * delta)
            score = _eri(w)
            rows.append({"component": key, "perturbation": f"{label}{delta}", "citywide_eri": round(score, 1)})
    scores = [r["citywide_eri"] for r in rows]
    return {
        "baseline_eri": round(baseline, 1),
        "delta": delta,
        "max_abs_change": round(max(abs(s - baseline) for s in scores), 1),
        "rows": rows,
    }


def cascade_propagation_sensitivity(
    delta: float = 0.15,
    n_iterations: int = 100,
    period: str = "midday",
) -> dict[str, Any]:
    """Perturb cascade conditional probabilities ±delta (fast MC, no file writes)."""
    from quaketwin.cascade.simulate import run_cascade_with_overrides

    base = run_cascade_with_overrides(period=period, n_iterations=n_iterations, propagation_overrides=None)
    base_delay = float(base["population_weighted"]["expected_delay_factor"])
    prop_base = base["propagation_baseline"]
    keys = ["substation_to_substation", "substation_to_tower", "substation_to_hospital"]
    rows = []
    for key in keys:
        for sign in (1, -1):
            val = max(0.05, min(0.95, float(prop_base[key]) + sign * delta))
            s = run_cascade_with_overrides(
                period=period, n_iterations=n_iterations, propagation_overrides={key: val}
            )
            d = float(s["population_weighted"]["expected_delay_factor"])
            rows.append({"parameter": key, "value": round(val, 3), "delay_factor": round(d, 4)})
    delays = [r["delay_factor"] for r in rows]
    return {
        "baseline_delay_factor": round(base_delay, 4),
        "n_iterations": n_iterations,
        "delta": delta,
        "max_pct_change": round(max(abs(d - base_delay) / base_delay * 100 for d in delays), 2),
        "rows": rows,
    }


def run_all_sensitivity_studies() -> dict[str, Any]:
    out = {
        "gmpe_weights": gmpe_weight_sensitivity(),
        "occupancy_multipliers": occupancy_multiplier_sensitivity(),
        "eri_weights": eri_weight_sensitivity(),
        "cascade_propagation": cascade_propagation_sensitivity(),
    }
    path = _root() / "outputs/sensitivity_studies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out
