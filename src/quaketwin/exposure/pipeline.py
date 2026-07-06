"""Diurnal exposure and casualty estimation pipeline (Phase 3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np

from quaketwin.config import ProjectSettings
from quaketwin.exposure.config import load_diurnal_config, period_keys
from quaketwin.exposure.casualties import expected_casualties_vectorized, load_casualty_rates


def _default_paths() -> dict[str, Path]:
    root = ProjectSettings().project_root
    return {
        "profiles": root / "data/processed/dhaka_building_profiles.gpkg",
        "output_gpkg": root / "data/processed/dhaka_exposure_diurnal.gpkg",
        "output_summary": root / "data/processed/diurnal_exposure_summary.json",
    }


def run_diurnal_exposure(
    profiles_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """
    Compute time-varying population and casualty exposure for each building.

    Adds columns: pop_{period}, casualties_{period} for each diurnal period.
    """
    paths = _default_paths()
    profiles_path = profiles_path or paths["profiles"]
    output_path = output_path or paths["output_gpkg"]
    cfg = load_diurnal_config()
    periods = period_keys(cfg)
    casualty_rates = load_casualty_rates(cfg)
    legacy_rate = float(cfg["casualty_model"].get("collapse_casualty_rate", 0.35))
    multipliers = cfg["occupancy_multipliers"]

    print(f"Loading {profiles_path}", flush=True)
    gdf = gpd.read_file(profiles_path)
    occ = gdf["occupancy_type"].fillna("residential")

    baseline_total = float(gdf["population_est"].sum())

    summary_rows = []
    for period in periods:
        mult = occ.map(lambda o, p=period: multipliers.get(o, multipliers["residential"]).get(p, 1.0))
        pop_col = f"pop_{period}"
        cas_col = f"casualties_{period}"

        # Population-conserving redistribution: multipliers set the relative
        # weight of each building at this hour, then the citywide total is
        # rescaled back to the static WorldPop baseline. People move between
        # buildings during the day; they do not leave the study area.
        raw = gdf["population_est"].to_numpy(dtype=float) * mult.to_numpy(dtype=float)
        raw_total = raw.sum()
        scale = baseline_total / raw_total if raw_total > 0 else 1.0
        gdf[pop_col] = np.round(raw * scale).astype(np.int32)
        gdf[cas_col] = expected_casualties_vectorized(
            gdf[pop_col].to_numpy(dtype=float),
            gdf["collapse_probability"].to_numpy(dtype=float),
            gdf["occupancy_type"],
            casualty_rates,
        )

        summary_rows.append(
            {
                "period": period,
                "label": cfg["diurnal_periods"][period]["label"],
                "hour": cfg["diurnal_periods"][period]["hour"],
                "total_population": int(gdf[pop_col].sum()),
                "expected_casualties": int(gdf[cas_col].sum()),
                "high_risk_population": int(
                    gdf.loc[gdf["collapse_probability"] >= 0.5, pop_col].sum()
                ),
                "redistribution_scale": round(scale, 4),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GPKG", layer="diurnal_exposure")

    summary = {
        "buildings": len(gdf),
        "casualty_model": "hazus_severity_stratified",
        "legacy_flat_rate": legacy_rate,
        "baseline_population_static": int(gdf["population_est"].sum()),
        "periods": summary_rows,
    }

    paths["output_summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Written: {output_path}", flush=True)
    return summary
