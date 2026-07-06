"""Overlay hazard + population on building footprints (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree

from quaketwin.config import ProjectSettings, load_config
from quaketwin.data.attributes import (
    _CONSTRUCTION_MAP,
    _DEFAULT_HEIGHT_M,
    _OCCUPANCY_MAP,
    infer_height_m,
    normalize_construction_type,
)
from quaketwin.data.heights import merge_open_buildings_heights
from quaketwin.geo.dhaka import haversine_km
from quaketwin.risk.fragility import _LOGISTIC_K, _MEDIAN_CAPACITY_G


def _default_paths() -> dict[str, Path]:
    root = ProjectSettings().project_root
    return {
        "buildings": root / "data/processed/dhaka_buildings.geojson",
        "hazard": root / "data/processed/hazard_mw72_dauki.geojson",
        "worldpop": root / "data/raw/population/worldpop_bgd_2020.tif",
        "output_gpkg": root / "data/processed/dhaka_building_profiles.gpkg",
        "output_geojson": root / "data/processed/dhaka_building_profiles.geojson",
    }


def _load_hazard_grid(hazard_path: Path) -> pd.DataFrame:
    with open(hazard_path, encoding="utf-8") as f:
        fc = json.load(f)
    rows = []
    for feat in fc["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        rows.append({"hazard_lon": lon, "hazard_lat": lat, **feat["properties"]})
    return pd.DataFrame(rows)


def _nearest_hazard_join(
    building_lon: np.ndarray,
    building_lat: np.ndarray,
    hazard_df: pd.DataFrame,
) -> pd.DataFrame:
    hazard_coords = np.column_stack([hazard_df["hazard_lon"].values, hazard_df["hazard_lat"].values])
    tree = cKDTree(hazard_coords)
    building_coords = np.column_stack([building_lon, building_lat])
    _, idx = tree.query(building_coords, k=1)
    return hazard_df.iloc[idx].reset_index(drop=True)


def _vectorized_construction(building_col: pd.Series) -> pd.Series:
    return building_col.fillna("yes").str.lower().map(_CONSTRUCTION_MAP).fillna("unknown")


def _vectorized_occupancy(building_col: pd.Series, amenity_col: pd.Series | None) -> pd.Series:
    occ = building_col.fillna("yes").str.lower().map(_OCCUPANCY_MAP).fillna("residential")
    if amenity_col is not None:
        am = amenity_col.fillna("").str.lower()
        occ = np.where(am.isin(["school", "college", "university"]), "education", occ)
        occ = np.where(am.isin(["hospital", "clinic"]), "healthcare", occ)
        occ = np.where(am.eq("place_of_worship"), "assembly", occ)
    return pd.Series(occ, index=building_col.index)


def _vectorized_height(gdf: pd.DataFrame, construction: pd.Series) -> pd.Series:
    levels = gdf["building:levels"] if "building:levels" in gdf.columns else None
    height = gdf["height"] if "height" in gdf.columns else None
    if levels is not None:
        lvl = pd.to_numeric(levels, errors="coerce")
        from_levels = lvl * 3.0
    else:
        from_levels = pd.Series(np.nan, index=gdf.index)
    if height is not None:
        h = height.astype(str).str.lower().str.replace("m", "", regex=False).str.strip()
        from_height = pd.to_numeric(h, errors="coerce")
    else:
        from_height = pd.Series(np.nan, index=gdf.index)
    default = construction.map(_DEFAULT_HEIGHT_M).fillna(6.0)
    return from_height.fillna(from_levels).fillna(default)


# Population plausibility bounds: very large OSM polygons (campuses, depots,
# airport aprons) otherwise absorb density x area estimates of 10k+ people.
_MAX_EFFECTIVE_FOOTPRINT_M2 = 20_000.0
_M2_PER_PERSON = 10.0
_FLOOR_HEIGHT_M = 3.0


def _vectorized_population(
    lons: np.ndarray,
    lats: np.ndarray,
    footprint_m2: np.ndarray,
    height_m: np.ndarray,
    worldpop_path: Path,
) -> np.ndarray:
    with rasterio.open(worldpop_path) as ds:
        res_lon, res_lat = ds.res
        m_per_deg_lat = 110_540
        samples = np.array([v[0] for v in ds.sample(zip(lons, lats))], dtype=float)
        m_per_deg_lon = 111_320 * np.cos(np.radians(lats))
        pixel_area = np.abs(res_lon * m_per_deg_lon * res_lat * m_per_deg_lat)
        density = np.where(pixel_area > 0, samples / pixel_area, 0.0)
        density = np.where(samples < 0, 0.0, density)
        effective_fp = np.minimum(footprint_m2, _MAX_EFFECTIVE_FOOTPRINT_M2)
        est = density * effective_fp
        # Structural capacity cap: floors x floor area / m2 per person
        floors = np.maximum(1.0, height_m / _FLOOR_HEIGHT_M)
        capacity = effective_fp * floors / _M2_PER_PERSON
        est = np.minimum(est, capacity)
        pop_est = np.maximum(0, np.round(est)).astype(np.int32)
    return pop_est


def _vectorized_collapse(
    amplified_pga: pd.Series,
    construction: pd.Series,
    liquefaction: pd.Series,
    height_m: pd.Series,
) -> pd.Series:
    medians = construction.map(_MEDIAN_CAPACITY_G).fillna(0.28)
    height_adj = ((height_m - 12).clip(lower=0) * 0.004).clip(upper=0.08)
    medians = medians - height_adj
    x = amplified_pga - medians
    base = 1.0 / (1.0 + np.exp(-_LOGISTIC_K * x))
    liq_boost = np.minimum(0.20, liquefaction * 0.25)
    return np.minimum(1.0, base + liq_boost).round(4)


def _vectorized_fire(collapse_p: pd.Series, occupancy: pd.Series, liquefaction: pd.Series) -> pd.Series:
    occ_factor = occupancy.map(
        {
            "industrial": 0.15,
            "commercial": 0.10,
            "residential": 0.06,
            "healthcare": 0.08,
        }
    ).fillna(0.05)
    return np.minimum(1.0, collapse_p * 0.4 + occ_factor + liquefaction * 0.05).round(4)


def build_building_profiles(
    buildings_path: Path | None = None,
    hazard_path: Path | None = None,
    worldpop_path: Path | None = None,
    output_path: Path | None = None,
    output_format: str = "gpkg",
    scenario_mw: float = 7.2,
) -> dict[str, Any]:
    """Join buildings with hazard, WorldPop, and fragility-based collapse risk."""
    paths = _default_paths()
    buildings_path = buildings_path or paths["buildings"]
    hazard_path = hazard_path or paths["hazard"]
    worldpop_path = worldpop_path or paths["worldpop"]
    if output_path is None:
        output_path = paths["output_gpkg"] if output_format == "gpkg" else paths["output_geojson"]

    cfg = load_config()
    fault = cfg["faults"]["dauki"]["reference_epicenter"]
    epic_lon, epic_lat = fault["lon"], fault["lat"]

    print(f"Loading buildings: {buildings_path}", flush=True)
    gdf = gpd.read_file(buildings_path)
    print(f"  {len(gdf):,} buildings", flush=True)

    gdf["building_id"] = gdf["osm_id"].astype(np.int64)
    building_col = gdf["building"] if "building" in gdf.columns else pd.Series("yes", index=gdf.index)
    amenity_col = gdf["amenity"] if "amenity" in gdf.columns else None

    gdf["construction_type"] = _vectorized_construction(building_col)
    gdf["occupancy_type"] = _vectorized_occupancy(building_col, amenity_col)

    print("Computing centroids...", flush=True)
    centroids = gdf.geometry.centroid
    lon = centroids.x.to_numpy()
    lat = centroids.y.to_numpy()
    gdf["lon"] = lon
    gdf["lat"] = lat

    base_height = _vectorized_height(gdf, gdf["construction_type"])
    gdf["height_m"], gdf["height_source"] = merge_open_buildings_heights(
        lon, lat, base_height.to_numpy()
    )

    lat_rad = np.radians(lat)
    gdf["footprint_m2"] = gdf.geometry.area * 111_320 * np.cos(lat_rad) * 110_540

    print(f"Joining hazard: {hazard_path.name}", flush=True)
    hazard_join = _nearest_hazard_join(lon, lat, _load_hazard_grid(hazard_path))
    for col in ("pga_g", "mmi", "amplified_pga_g", "soil_zone_code", "liquefaction_index", "scenario_id"):
        gdf[col] = hazard_join[col].values

    print("Sampling WorldPop...", flush=True)
    gdf["population_est"] = _vectorized_population(
        lon, lat, gdf["footprint_m2"].to_numpy(), gdf["height_m"].to_numpy(), worldpop_path
    )

    print("Computing risk metrics...", flush=True)
    gdf["dist_fault_km"] = [haversine_km(epic_lon, epic_lat, lo, la) for lo, la in zip(lon, lat)]
    gdf["liquefaction_index"] = gdf["liquefaction_index"].astype(float)
    gdf["collapse_probability"] = _vectorized_collapse(
        gdf["amplified_pga_g"], gdf["construction_type"], gdf["liquefaction_index"], gdf["height_m"]
    )
    gdf["fire_probability"] = _vectorized_fire(
        gdf["collapse_probability"], gdf["occupancy_type"], gdf["liquefaction_index"]
    )
    pop_factor = 1 + gdf["population_est"].clip(upper=50) / 50
    gdf["recovery_priority"] = (gdf["collapse_probability"] * pop_factor).round(4)

    # Keep thesis-relevant columns only
    keep = [
        "building_id", "lon", "lat", "construction_type", "height_m", "occupancy_type",
        "population_est", "footprint_m2", "height_source", "pga_g", "mmi", "amplified_pga_g", "soil_zone_code",
        "liquefaction_index", "dist_fault_km", "collapse_probability", "fire_probability",
        "recovery_priority", "scenario_id", "geometry",
    ]
    if "building" in gdf.columns:
        keep.insert(3, "building")
    gdf = gdf[[c for c in keep if c in gdf.columns]].set_crs("EPSG:4326")

    print(f"Writing {output_format}: {output_path}", flush=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    driver = "GPKG" if output_format == "gpkg" else "GeoJSON"
    gdf.to_file(output_path, driver=driver, layer="building_profiles" if output_format == "gpkg" else None)

    summary = {
        "buildings": len(gdf),
        "output": str(output_path),
        "format": output_format,
        "scenario_mw": scenario_mw,
        "mean_collapse_p": round(float(gdf["collapse_probability"].mean()), 4),
        "high_risk_pct": round(float((gdf["collapse_probability"] >= 0.5).mean()) * 100, 2),
        "total_population_est": int(gdf["population_est"].sum()),
    }
    print(json.dumps(summary, indent=2), flush=True)
    return summary
