from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from quaketwin.geo.dhaka import haversine_km
from quaketwin.hazard.scenario import EarthquakeScenario
from quaketwin.config import ProjectSettings


def _load_gmpe_config() -> dict[str, Any]:
    path = ProjectSettings().project_root / "config" / "hazard_gmpe.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _pga_single(mw: float, r_rup_km: float, depth_km: float, coeffs: dict[str, float]) -> float:
    h = depth_km * 0.5
    r2 = max(r_rup_km**2 + h**2, 1.0)
    ln_pga = coeffs["intercept"] + coeffs["mw_coeff"] * mw - coeffs["ln_r2_coeff"] * math.log(r2)
    return max(1e-4, math.exp(ln_pga))


def pga_logic_tree(mw: float, r_rup_km: float, depth_km: float) -> dict[str, float]:
    """Weighted-mean PGA plus inter-model spread (logic-tree uncertainty)."""
    cfg = _load_gmpe_config()
    pgas: list[float] = []
    weights: list[float] = []
    by_model: dict[str, float] = {}
    for branch in cfg["logic_tree"]:
        pga = _pga_single(mw, r_rup_km, depth_km, branch)
        w = float(branch["weight"])
        pgas.append(pga)
        weights.append(w)
        by_model[branch["id"]] = round(pga, 4)
    mean = sum(p * w for p, w in zip(pgas, weights)) / sum(weights)
    spread = max(pgas) - min(pgas)
    return {
        "pga_g": mean,
        "pga_spread_g": spread,
        "pga_by_model": by_model,
    }


def pga_to_mmi(pga_g: float) -> float:
    """Empirical PGA (g) -> MMI (Worden et al. 2012 simplified)."""
    if pga_g <= 0:
        return 1.0
    pga_cms2 = pga_g * 981.0
    return max(1.0, min(12.0, 3.66 + 2.01 * math.log10(pga_cms2)))


def compute_ground_motion_grid(
    grid: list[dict],
    scenario: EarthquakeScenario,
) -> list[dict]:
    """Attach logic-tree PGA (g), uncertainty spread, and MMI to each grid cell."""
    results = []
    for cell in grid:
        dist_km = haversine_km(
            scenario.epicenter_lon,
            scenario.epicenter_lat,
            cell["lon"],
            cell["lat"],
        )
        lt = pga_logic_tree(scenario.magnitude, dist_km, scenario.depth_km)
        pga = lt["pga_g"]
        results.append(
            {
                **cell,
                "distance_km": round(dist_km, 2),
                "pga_g": pga,
                "pga_spread_g": round(lt["pga_spread_g"], 4),
                "pga_by_model": lt["pga_by_model"],
                "mmi": pga_to_mmi(pga),
            }
        )
    return results
