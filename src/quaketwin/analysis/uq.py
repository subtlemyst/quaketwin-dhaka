"""Latin Hypercube uncertainty propagation over coupled citywide metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from scipy.stats import qmc

from quaketwin.config import ProjectSettings, load_config
from quaketwin.exposure.casualties import expected_casualties_vectorized, load_casualty_rates
from quaketwin.geo.dhaka import haversine_km
from quaketwin.hazard.ground_motion import _load_gmpe_config, _pga_single, pga_logic_tree
from quaketwin.hazard.scenario import load_default_scenario
from quaketwin.resilience.pipeline import load_resilience_config
from quaketwin.risk.fragility import _LOGISTIC_K, _MEDIAN_CAPACITY_G

_PARAM_BOUNDS = {
    "w_boore": (0.40, 0.60),
    "capacity_shift_g": (-0.03, 0.03),
    "logistic_k_scale": (0.85, 1.15),
    "substation_to_substation": (0.15, 0.45),
    "substation_to_tower": (0.50, 0.80),
    "non_res_occ_scale": (0.80, 1.20),
}


def _collapse_vectorized(
    amp_pga: np.ndarray,
    construction: np.ndarray,
    liq: np.ndarray,
    height: np.ndarray,
    capacity_shift: float,
    k_scale: float,
) -> np.ndarray:
    medians = np.array(
        [_MEDIAN_CAPACITY_G.get(str(c), 0.28) for c in construction], dtype=float
    )
    medians -= np.minimum(0.08, np.maximum(0, (height - 12) * 0.004))
    medians += capacity_shift
    x = amp_pga - medians
    k = _LOGISTIC_K * k_scale
    base = 1.0 / (1.0 + np.exp(-k * x))
    liq_boost = np.minimum(0.20, liq * 0.25)
    return np.clip(base + liq_boost, 0.0, 1.0)


def _pga_scale_from_weight(w_boore: float, dist_km: float, depth_km: float, mw: float) -> float:
    cfg = _load_gmpe_config()
    branches = cfg["logic_tree"]
    w1 = w_boore
    w2 = 1.0 - w1
    pgas = [_pga_single(mw, dist_km, depth_km, branches[0]), _pga_single(mw, dist_km, depth_km, branches[1])]
    new_pga = (w1 * pgas[0] + w2 * pgas[1]) / (w1 + w2)
    baseline = pga_logic_tree(mw, dist_km, depth_km)["pga_g"]
    return float(new_pga / max(baseline, 1e-9))


def _delay_surrogate(sub_sub: float, sub_tower: float, sub_hosp: float, baseline: float = 1.9015) -> float:
    """Empirical delay factor from cascade sensitivity (fast surrogate for LHS)."""
    return float(
        baseline
        * (1.0 + 0.35 * (sub_sub - 0.30) / 0.30)
        * (1.0 + 0.08 * (sub_tower - 0.65) / 0.65)
        * (1.0 + 0.02 * (sub_hosp - 0.30) / 0.30)
    )


def _eri_from_components(
    mean_collapse: float,
    casualties: float,
    delay: float,
    mean_response_min: float,
    weights: dict[str, float],
    baseline_casualties: float,
    baseline_overload: float,
) -> float:
    structural = 1.0 - mean_collapse
    cas_ratio = casualties / max(baseline_casualties, 1)
    emergency = 1.0 - min(1.0, baseline_overload * cas_ratio)
    lifeline = float(np.clip(1.0 - (delay - 1.0) / 2.0, 0, 1))
    access = 1.0 / (1.0 + mean_response_min / 30.0)
    return 100.0 * sum(weights[k] * v for k, v in zip(
        ["structural", "emergency_capacity", "lifeline_robustness", "accessibility"],
        [structural, emergency, lifeline, access],
    ))


def _ci95(arr: np.ndarray) -> list[float]:
    return [round(float(np.percentile(arr, 2.5)), 4), round(float(np.percentile(arr, 97.5)), 4)]


def run_latin_hypercube_uq(n_samples: int = 128, seed: int = 42) -> dict[str, Any]:
    root = ProjectSettings().project_root
    b = gpd.read_file(root / "data/processed/dhaka_building_profiles.gpkg", layer="building_profiles")
    resp = gpd.read_file(root / "data/processed/dhaka_response_phase4.gpkg", layer="response_buildings")
    hospitals = gpd.read_file(root / "data/processed/dhaka_hospital_load_phase4.gpkg", layer="hospital_load")

    with open(root / "config/diurnal_exposure.yaml", encoding="utf-8") as f:
        diurnal_cfg = yaml.safe_load(f)
    rates = load_casualty_rates(diurnal_cfg)
    mult = diurnal_cfg["occupancy_multipliers"]
    period = "midday"

    scenario = load_default_scenario()
    cfg = load_config()
    center = cfg["study_area"]["center"]
    epic = cfg["faults"]["dauki"]["reference_epicenter"]
    dist_km = haversine_km(epic["lon"], epic["lat"], center["lon"], center["lat"])

    amp = b["amplified_pga_g"].to_numpy(dtype=float)
    construction = b["construction_type"].fillna("unknown").to_numpy()
    liq = b["liquefaction_index"].to_numpy(dtype=float)
    height = b["height_m"].to_numpy(dtype=float) if "height_m" in b.columns else np.full(len(b), 6.0)
    pop_static = b["population_est"].to_numpy(dtype=float)
    occ = b["occupancy_type"].fillna("residential") if "occupancy_type" in b.columns else pd.Series(["residential"] * len(b))
    base_mult = occ.map(lambda o: float(mult.get(o, mult["residential"]).get(period, 1.0))).to_numpy(dtype=float)

    baseline_collapse = _collapse_vectorized(amp, construction, liq, height, 0.0, 1.0)
    raw_base = pop_static * base_mult
    scale_base = pop_static.sum() / max(raw_base.sum(), 1e-9)
    pop_mid = raw_base * scale_base
    baseline_cas = float(expected_casualties_vectorized(pop_mid, baseline_collapse, occ, rates).sum())
    baseline_overload = float(hospitals["overload_ratio"].clip(upper=10).mean()) / 10.0
    mean_resp = float(resp["response_time_min"].mean())
    w_eri = load_resilience_config()["weights"]

    names = list(_PARAM_BOUNDS.keys())
    bounds = np.array([_PARAM_BOUNDS[n] for n in names])
    sampler = qmc.LatinHypercube(d=len(names), seed=seed)
    unit = sampler.random(n_samples)
    samples = qmc.scale(unit, bounds[:, 0], bounds[:, 1])

    records = {
        "mean_collapse_p": [],
        "midday_casualties": [],
        "hospital_overload_ratio": [],
        "delay_factor": [],
        "citywide_eri": [],
    }

    for row in samples:
        params = dict(zip(names, row))
        pga_s = _pga_scale_from_weight(float(params["w_boore"]), dist_km, scenario.depth_km, scenario.magnitude)
        amp_s = amp * pga_s
        collapse = _collapse_vectorized(
            amp_s, construction, liq, height,
            float(params["capacity_shift_g"]),
            float(params["logistic_k_scale"]),
        )
        m = np.where(occ.to_numpy() != "residential", base_mult * float(params["non_res_occ_scale"]), base_mult)
        raw = pop_static * m
        scale_t = pop_static.sum() / max(raw.sum(), 1e-9)
        pop_t = raw * scale_t
        cas = float(expected_casualties_vectorized(pop_t, collapse, occ, rates).sum())
        delay = _delay_surrogate(
            float(params["substation_to_substation"]),
            float(params["substation_to_tower"]),
            0.30,
        )
        overload = min(1.0, baseline_overload * (cas / max(baseline_cas, 1)))
        eri = _eri_from_components(
            float(collapse.mean()), cas, delay, mean_resp, w_eri, baseline_cas, baseline_overload
        )
        records["mean_collapse_p"].append(float(collapse.mean()))
        records["midday_casualties"].append(cas)
        records["hospital_overload_ratio"].append(overload)
        records["delay_factor"].append(delay)
        records["citywide_eri"].append(eri)

    summary: dict[str, Any] = {
        "method": "latin_hypercube",
        "n_samples": n_samples,
        "seed": seed,
        "parameters": {n: list(_PARAM_BOUNDS[n]) for n in names},
        "metrics": {},
    }
    for key, vals in records.items():
        arr = np.array(vals)
        summary["metrics"][key] = {
            "mean": round(float(arr.mean()), 4),
            "std": round(float(arr.std(ddof=1)), 4),
            "ci95": _ci95(arr),
            "min": round(float(arr.min()), 4),
            "max": round(float(arr.max()), 4),
        }

    out = root / "outputs/latin_hypercube_uq.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
