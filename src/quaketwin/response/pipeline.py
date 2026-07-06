"""Phase 4 hospital overload and rescue priority pipeline."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from scipy.spatial import cKDTree

from quaketwin.config import ProjectSettings
from quaketwin.response.routing import travel_minutes_to_assigned_hospitals


def _default_paths() -> dict[str, Path]:
    root = ProjectSettings().project_root
    return {
        "profiles": root / "data/processed/dhaka_exposure_diurnal.gpkg",
        "roads": root / "data/processed/dhaka_roads.geojson",
        "hospitals": root / "data/processed/dhaka_hospitals.geojson",
        "output_buildings": root / "data/processed/dhaka_response_phase4.gpkg",
        "output_hospitals": root / "data/processed/dhaka_hospital_load_phase4.gpkg",
        "output_summary": root / "data/processed/response_phase4_summary.json",
    }


@lru_cache
def load_response_config(path: Path | None = None) -> dict[str, Any]:
    root = ProjectSettings().project_root
    cfg_path = path or root / "config" / "response.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _capacity_from_row(row: pd.Series, cfg: dict[str, Any]) -> int:
    amenity = str(row.get("amenity") or "").lower()
    healthcare = str(row.get("healthcare") or "").lower()
    name = str(row.get("name") or "").lower()
    cap = cfg["hospital_capacity"]["amenity_capacity"].get(amenity)
    if cap is None:
        cap = cfg["hospital_capacity"]["healthcare_capacity"].get(healthcare)
    if cap is None:
        cap = cfg["hospital_capacity"]["default_beds"]
    if "medical college" in name:
        cap *= 2.0
    if "specialized" in name:
        cap *= 1.5
    factor = cfg["hospital_capacity"]["bed_to_emergency_capacity_factor"]
    cap = int(round(cap * factor))
    return int(np.clip(cap, cfg["hospital_capacity"]["min_capacity"], cfg["hospital_capacity"]["max_capacity"]))


def _coords(gdf: gpd.GeoDataFrame) -> np.ndarray:
    geom = gdf.geometry
    cent = geom if geom.geom_type.isin(["Point"]).all() else geom.to_crs(3857).centroid.to_crs(4326)
    return np.column_stack([cent.x.to_numpy(), cent.y.to_numpy()])


def run_response_model(
    period: str | None = None,
    profiles_path: Path | None = None,
    roads_path: Path | None = None,
    hospitals_path: Path | None = None,
) -> dict[str, Any]:
    """Compute hospital overload and building rescue priority."""
    cfg = load_response_config()
    paths = _default_paths()
    period = period or cfg["default_period"]
    profiles_path = profiles_path or paths["profiles"]
    roads_path = roads_path or paths["roads"]
    hospitals_path = hospitals_path or paths["hospitals"]

    pop_col = f"pop_{period}"
    cas_col = f"casualties_{period}"

    if not profiles_path.exists():
        raise FileNotFoundError(f"Missing profiles file: {profiles_path}")
    if not roads_path.exists():
        raise FileNotFoundError(f"Missing roads file: {roads_path}")
    if not hospitals_path.exists():
        raise FileNotFoundError(f"Missing hospitals file: {hospitals_path}")

    print(f"Loading {profiles_path.name}", flush=True)
    buildings = gpd.read_file(profiles_path)
    if pop_col not in buildings.columns or cas_col not in buildings.columns:
        raise ValueError(f"Expected {pop_col} and {cas_col}; run Phase 3 first.")

    print(f"Loading {roads_path.name}", flush=True)
    roads = gpd.read_file(roads_path)
    print(f"Loading {hospitals_path.name}", flush=True)
    hospitals = gpd.read_file(hospitals_path)

    # Hospital capacities
    hospitals["emergency_capacity"] = hospitals.apply(lambda r: _capacity_from_row(r, cfg), axis=1)
    hosp_xy = _coords(hospitals)
    hosp_tree = cKDTree(hosp_xy)

    b_xy = np.column_stack([buildings["lon"].to_numpy(), buildings["lat"].to_numpy()])
    _, hosp_idx = hosp_tree.query(b_xy, k=1)
    buildings["hospital_id"] = hospitals.iloc[hosp_idx]["osm_id"].to_numpy()
    buildings["hospital_name"] = hospitals.iloc[hosp_idx]["name"].fillna("Unnamed facility").to_numpy()

    # Straight-line travel proxy
    b_pt = gpd.points_from_xy(buildings["lon"], buildings["lat"], crs="EPSG:4326").to_crs(3857)
    h_cent = hospitals.iloc[hosp_idx].copy()
    h_cent.geometry = h_cent.geometry.to_crs(3857).centroid.to_crs(4326)
    h_pt = gpd.points_from_xy(h_cent.geometry.x, h_cent.geometry.y, crs="EPSG:4326").to_crs(3857)
    buildings["dist_hospital_m"] = gpd.GeoSeries(b_pt, index=buildings.index).distance(
        gpd.GeoSeries(h_pt, index=buildings.index), align=False
    ).to_numpy()

    # Nearest road and access proxy
    road_xy = _coords(roads)
    road_tree = cKDTree(road_xy)
    _, road_idx = road_tree.query(b_xy, k=1)
    buildings["nearest_road_class"] = roads.iloc[road_idx]["highway"].fillna("unclassified").to_numpy()
    r_cent = roads.iloc[road_idx].copy()
    r_cent.geometry = r_cent.geometry.to_crs(3857).centroid.to_crs(4326)
    r_pt = gpd.points_from_xy(r_cent.geometry.x, r_cent.geometry.y, crs="EPSG:4326").to_crs(3857)
    buildings["dist_road_m"] = gpd.GeoSeries(b_pt, index=buildings.index).distance(
        gpd.GeoSeries(r_pt, index=buildings.index), align=False
    ).to_numpy()

    speed_map = cfg["road_access"]["speed_kmh"]
    speed_kmh = buildings["nearest_road_class"].map(speed_map).fillna(10.0).astype(float)
    base_travel_min = buildings["dist_hospital_m"] / (speed_kmh * 1000 / 60)

    print("Computing network routing travel times...", flush=True)
    assigned_h_lon = h_cent.geometry.x.to_numpy()
    assigned_h_lat = h_cent.geometry.y.to_numpy()

    network_min = travel_minutes_to_assigned_hospitals(
        buildings["lon"].to_numpy(),
        buildings["lat"].to_numpy(),
        assigned_h_lon,
        assigned_h_lat,
        roads,
        speed_map,
    )
    use_network = np.isfinite(network_min)
    buildings["network_travel_min"] = np.where(use_network, network_min, base_travel_min).round(2)
    buildings["routing_method"] = np.where(use_network, "network", "straight_line")

    # Local blockage from nearby severe-collapse buildings
    severe = buildings.loc[buildings["collapse_probability"] >= cfg["rescue_priority"]["severe_collapse_threshold"]]
    if len(severe) > 0:
        severe_xy = np.column_stack([severe["lon"].to_numpy(), severe["lat"].to_numpy()])
        severe_tree = cKDTree(severe_xy)
        radius_deg = cfg["road_access"]["blockage_distance_m"] / 111_320
        nearby = severe_tree.query_ball_point(b_xy, r=radius_deg)
        nearby_counts = np.array([len(x) for x in nearby], dtype=float)
    else:
        nearby_counts = np.zeros(len(buildings), dtype=float)

    blockage_delay = np.minimum(
        nearby_counts * cfg["road_access"]["blockage_delay_minutes_per_nearby_high_risk_building"],
        cfg["road_access"]["max_blockage_delay_minutes"],
    )
    buildings["road_blockage_delay_min"] = blockage_delay.round(2)
    buildings["response_time_min"] = (
        buildings["network_travel_min"] + blockage_delay + buildings["dist_road_m"] / 60
    ).round(2)

    casualty = buildings[cas_col].astype(float)
    access_score = 1 / np.maximum(buildings["response_time_min"], 1)
    w = cfg["rescue_priority"]
    buildings["rescue_priority_score"] = (
        w["casualty_weight"] * casualty / max(float(casualty.max()), 1.0)
        + w["collapse_weight"] * buildings["collapse_probability"]
        + w["access_weight"] * access_score / max(float(access_score.max()), 1.0)
    ).round(4)

    hospitals_load = (
        buildings.groupby(["hospital_id", "hospital_name"], as_index=False)
        .agg(
            assigned_buildings=("building_id", "count"),
            incoming_casualties=(cas_col, "sum"),
            mean_response_time_min=("response_time_min", "mean"),
        )
    )
    hospitals_load = hospitals.merge(hospitals_load, left_on="osm_id", right_on="hospital_id", how="left")
    hospitals_load["assigned_buildings"] = hospitals_load["assigned_buildings"].fillna(0).astype(int)
    hospitals_load["incoming_casualties"] = hospitals_load["incoming_casualties"].fillna(0).astype(int)
    hospitals_load["mean_response_time_min"] = hospitals_load["mean_response_time_min"].fillna(0).round(2)
    hospitals_load["overload_ratio"] = (
        hospitals_load["incoming_casualties"] / hospitals_load["emergency_capacity"].replace(0, np.nan)
    ).fillna(0).round(3)
    hospitals_load["overloaded"] = hospitals_load["overload_ratio"] > 1.0

    top_buildings = (
        buildings.sort_values("rescue_priority_score", ascending=False)
        .head(50)[
            [
                "building_id",
                "collapse_probability",
                pop_col,
                cas_col,
                "hospital_name",
                "response_time_min",
                "rescue_priority_score",
            ]
        ]
        .to_dict(orient="records")
    )

    paths["output_buildings"].parent.mkdir(parents=True, exist_ok=True)
    buildings.to_file(paths["output_buildings"], driver="GPKG", layer="response_buildings")
    hospitals_load.to_file(paths["output_hospitals"], driver="GPKG", layer="hospital_load")

    summary = {
        "period": period,
        "buildings": len(buildings),
        "hospitals": len(hospitals_load),
        "total_expected_casualties": int(buildings[cas_col].sum()),
        "mean_response_time_min": round(float(buildings["response_time_min"].mean()), 2),
        "network_routed_pct": round(float((buildings["routing_method"] == "network").mean()) * 100, 1),
        "overloaded_hospitals": int(hospitals_load["overloaded"].sum()),
        "max_overload_ratio": round(float(hospitals_load["overload_ratio"].max()), 3),
        "top_buildings": top_buildings[:10],
    }
    paths["output_summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return summary
