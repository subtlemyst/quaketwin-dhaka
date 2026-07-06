"""Vs30 class perturbation sensitivity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np

from quaketwin.config import ProjectSettings
from quaketwin.hazard.site import sample_vs30
from quaketwin.risk.fragility import _LOGISTIC_K, _MEDIAN_CAPACITY_G


def _collapse_vectorized(
    amp_pga: np.ndarray,
    construction: np.ndarray,
    liq: np.ndarray,
    height: np.ndarray,
) -> np.ndarray:
    medians = np.array(
        [_MEDIAN_CAPACITY_G.get(str(c), 0.28) for c in construction], dtype=float
    )
    medians -= np.minimum(0.08, np.maximum(0, (height - 12) * 0.004))
    x = amp_pga - medians
    base = 1.0 / (1.0 + np.exp(-_LOGISTIC_K * x))
    liq_boost = np.minimum(0.20, liq * 0.25)
    return np.clip(base + liq_boost, 0.0, 1.0)


def _amplified_pga(bedrock: np.ndarray, vs30: np.ndarray) -> np.ndarray:
    from quaketwin.hazard.site import _MA_ANCHORS, _VREF

    pgas = np.array([p for p, _ in _MA_ANCHORS])
    mas = np.array([m for _, m in _MA_ANCHORS])
    ma = np.interp(bedrock, pgas, mas)
    return bedrock * (_VREF / np.maximum(vs30, 100.0)) ** ma


def vs30_class_sensitivity(perturb_pct: float = 0.20) -> dict[str, Any]:
    """Perturb Vs30 ±20% and recompute mean collapse probability (building sample)."""
    root = ProjectSettings().project_root
    b = gpd.read_file(root / "data/processed/dhaka_building_profiles.gpkg", layer="building_profiles")
    # Subsample for speed if huge
    if len(b) > 100_000:
        b = b.sample(n=100_000, random_state=42)

    lon = b["lon"].to_numpy()
    lat = b["lat"].to_numpy()
    vs30 = sample_vs30(lon, lat)
    if vs30 is None:
        return {"error": "Vs30 raster not found", "skipped": True}

    bedrock = b["pga_g"].to_numpy(dtype=float)
    construction = b["construction_type"].fillna("unknown")
    liq = b["liquefaction_index"].to_numpy(dtype=float)
    height = b["height_m"].to_numpy(dtype=float) if "height_m" in b.columns else np.full(len(b), 6.0)

    def _mean_collapse(vs30_arr: np.ndarray) -> float:
        amp = _amplified_pga(bedrock, vs30_arr)
        return float(_collapse_vectorized(amp, construction.to_numpy(), liq, height).mean())

    base = _mean_collapse(vs30)
    low = _mean_collapse(vs30 * (1.0 - perturb_pct))
    high = _mean_collapse(vs30 * (1.0 + perturb_pct))
    return {
        "perturb_pct": perturb_pct,
        "vs30_range_observed": [round(float(vs30.min()), 1), round(float(vs30.max()), 1)],
        "mean_collapse_baseline": round(base, 4),
        "mean_collapse_vs30_low": round(low, 4),
        "mean_collapse_vs30_high": round(high, 4),
        "max_pct_change": round(max(abs(low - base), abs(high - base)) / max(base, 1e-9) * 100, 2),
        "n_buildings_sampled": len(b),
    }


def run_vs30_sensitivity() -> dict[str, Any]:
    result = vs30_class_sensitivity()
    path = ProjectSettings().project_root / "outputs/vs30_sensitivity.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
