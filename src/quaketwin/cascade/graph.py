"""Build the Dhaka lifeline-infrastructure dependency graph (Phase 5).

Node types
----------
- ``power``     : substations / plants / generators (OSM ``power=*``)
- ``comm_tower``: communication towers and masts
- ``bridge``    : highway bridges (access chokepoints)
- ``hospital``  : hospitals and clinics (Phase 4 layer)
- ``zone``      : ~1.1 km aggregation cells of the 706k building stock,
                  carrying population, expected casualties and mean collapse risk

Edges are *service dependencies* (provider -> dependent) wired by spatial
proximity, plus an undirected power-grid interconnect between substations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import yaml
from scipy.spatial import cKDTree

from quaketwin.config import ProjectSettings


def load_cascade_config() -> dict[str, Any]:
    root = ProjectSettings().project_root
    with open(root / "config" / "cascade.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _default_paths() -> dict[str, Path]:
    root = ProjectSettings().project_root
    return {
        "infrastructure": root / "data/processed/dhaka_infrastructure.geojson",
        "hospitals": root / "data/processed/dhaka_hospitals.geojson",
        "exposure": root / "data/processed/dhaka_exposure_diurnal.gpkg",
        "hazard": root / "data/processed/hazard_mw72_dauki.geojson",
    }


def _hazard_lookup(hazard_path: Path) -> tuple[cKDTree, pd.DataFrame]:
    with open(hazard_path, encoding="utf-8") as f:
        fc = json.load(f)
    rows = []
    for feat in fc["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        p = feat["properties"]
        rows.append(
            {
                "lon": lon,
                "lat": lat,
                "amplified_pga_g": p["amplified_pga_g"],
                "liquefaction_index": float(p["liquefaction_index"]),
            }
        )
    df = pd.DataFrame(rows)
    tree = cKDTree(df[["lon", "lat"]].to_numpy())
    return tree, df


def _sample_hazard(tree: cKDTree, hazard_df: pd.DataFrame, lons: np.ndarray, lats: np.ndarray) -> pd.DataFrame:
    _, idx = tree.query(np.column_stack([lons, lats]), k=1)
    return hazard_df.iloc[idx][["amplified_pga_g", "liquefaction_index"]].reset_index(drop=True)


def _point_lonlat(gdf: gpd.GeoDataFrame) -> tuple[np.ndarray, np.ndarray]:
    geom = gdf.geometry
    is_point = geom.geom_type.eq("Point")
    if is_point.all():
        return geom.x.to_numpy(), geom.y.to_numpy()
    cent = geom.to_crs(3857).centroid.to_crs(4326)
    return cent.x.to_numpy(), cent.y.to_numpy()


def _build_zones(exposure_path: Path, cell_deg: float, period: str) -> pd.DataFrame:
    cols = ["lon", "lat", f"pop_{period}", f"casualties_{period}", "collapse_probability"]
    gdf = gpd.read_file(exposure_path, columns=cols, ignore_geometry=True)
    df = pd.DataFrame(gdf)
    df["zx"] = np.floor(df["lon"] / cell_deg).astype(int)
    df["zy"] = np.floor(df["lat"] / cell_deg).astype(int)
    zones = (
        df.groupby(["zx", "zy"])
        .agg(
            population=(f"pop_{period}", "sum"),
            casualties=(f"casualties_{period}", "sum"),
            mean_collapse_p=("collapse_probability", "mean"),
            buildings=("lon", "size"),
        )
        .reset_index()
    )
    zones["lon"] = (zones["zx"] + 0.5) * cell_deg
    zones["lat"] = (zones["zy"] + 0.5) * cell_deg
    zones = zones[zones["population"] > 0].reset_index(drop=True)
    return zones


def _knn_edges(
    src_coords: np.ndarray,
    dst_coords: np.ndarray,
    k: int,
) -> list[tuple[int, int, float]]:
    """For each dst point return its k nearest src indices: (src_i, dst_j, dist_deg)."""
    if len(src_coords) == 0 or len(dst_coords) == 0:
        return []
    k_eff = min(k, len(src_coords))
    tree = cKDTree(src_coords)
    dist, idx = tree.query(dst_coords, k=k_eff)
    if k_eff == 1:
        dist = dist[:, None]
        idx = idx[:, None]
    edges = []
    for j in range(len(dst_coords)):
        for m in range(k_eff):
            edges.append((int(idx[j, m]), j, float(dist[j, m])))
    return edges


def build_infrastructure_graph(
    period: str = "midday",
    hazard_path: Path | None = None,
) -> nx.DiGraph:
    """Assemble the typed dependency graph with hazard attributes on every node."""
    cfg = load_cascade_config()
    paths = _default_paths()
    dep = cfg["dependencies"]

    hazard_file = hazard_path or paths["hazard"]
    tree, hazard_df = _hazard_lookup(hazard_file)

    infra = gpd.read_file(paths["infrastructure"])
    kind = infra["infra_kind"].astype(str)
    power_mask = kind.str.startswith("power_")
    infra["node_type"] = np.where(power_mask, "power", kind)

    hospitals = gpd.read_file(paths["hospitals"])
    zones = _build_zones(paths["exposure"], float(cfg["zone_cell_deg"]), period)

    g = nx.DiGraph()
    coords: dict[str, np.ndarray] = {}
    ids: dict[str, list[str]] = {}

    for node_type in ("power", "comm_tower", "bridge"):
        sub = infra[infra["node_type"] == node_type]
        lons, lats = _point_lonlat(sub) if len(sub) else (np.array([]), np.array([]))
        haz = (
            _sample_hazard(tree, hazard_df, lons, lats)
            if len(sub)
            else pd.DataFrame(columns=["amplified_pga_g", "liquefaction_index"])
        )
        node_ids = []
        for i, (_, row) in enumerate(sub.iterrows()):
            nid = f"{node_type}_{row['osm_id']}"
            g.add_node(
                nid,
                node_type=node_type,
                infra_kind=row["infra_kind"],
                name=str(row.get("name", "") or ""),
                lon=float(lons[i]),
                lat=float(lats[i]),
                amplified_pga_g=float(haz["amplified_pga_g"].iloc[i]),
                liquefaction_index=float(haz["liquefaction_index"].iloc[i]),
            )
            node_ids.append(nid)
        coords[node_type] = np.column_stack([lons, lats]) if len(sub) else np.empty((0, 2))
        ids[node_type] = node_ids

    h_lons, h_lats = _point_lonlat(hospitals)
    h_haz = _sample_hazard(tree, hazard_df, h_lons, h_lats)
    hosp_ids = []
    for i, (_, row) in enumerate(hospitals.iterrows()):
        nid = f"hospital_{row['osm_id']}"
        g.add_node(
            nid,
            node_type="hospital",
            name=str(row.get("name", "") or ""),
            lon=float(h_lons[i]),
            lat=float(h_lats[i]),
            amplified_pga_g=float(h_haz["amplified_pga_g"].iloc[i]),
            liquefaction_index=float(h_haz["liquefaction_index"].iloc[i]),
        )
        hosp_ids.append(nid)
    coords["hospital"] = np.column_stack([h_lons, h_lats])
    ids["hospital"] = hosp_ids

    z_haz = _sample_hazard(tree, hazard_df, zones["lon"].to_numpy(), zones["lat"].to_numpy())
    zone_ids = []
    for i, row in zones.iterrows():
        nid = f"zone_{int(row['zx'])}_{int(row['zy'])}"
        g.add_node(
            nid,
            node_type="zone",
            lon=float(row["lon"]),
            lat=float(row["lat"]),
            population=int(row["population"]),
            casualties=int(row["casualties"]),
            mean_collapse_p=float(row["mean_collapse_p"]),
            buildings=int(row["buildings"]),
            amplified_pga_g=float(z_haz["amplified_pga_g"].iloc[i]),
            liquefaction_index=float(z_haz["liquefaction_index"].iloc[i]),
        )
        zone_ids.append(nid)
    coords["zone"] = zones[["lon", "lat"]].to_numpy()
    ids["zone"] = zone_ids

    def wire(src_type: str, dst_type: str, k: int, service: str) -> None:
        for si, dj, dist in _knn_edges(coords[src_type], coords[dst_type], k):
            g.add_edge(ids[src_type][si], ids[dst_type][dj], service=service, dist_deg=dist)

    # Power-grid interconnect (undirected -> both directions)
    for si, dj, dist in _knn_edges(coords["power"], coords["power"], int(dep["substation_neighbors"]) + 1):
        a, b = ids["power"][si], ids["power"][dj]
        if a != b:
            g.add_edge(a, b, service="grid", dist_deg=dist)
            g.add_edge(b, a, service="grid", dist_deg=dist)

    wire("power", "comm_tower", int(dep["tower_substations"]), "power")
    wire("power", "hospital", int(dep["hospital_substations"]), "power")
    wire("comm_tower", "hospital", int(dep["hospital_towers"]), "comm")
    wire("power", "zone", int(dep["zone_substations"]), "power")
    wire("comm_tower", "zone", int(dep["zone_towers"]), "comm")

    # Bridges: access dependency for zones within radius
    radius_deg = float(dep["zone_bridges_within_km"]) / 111.0
    if len(coords["bridge"]) and len(coords["zone"]):
        btree = cKDTree(coords["bridge"])
        nearby = btree.query_ball_point(coords["zone"], r=radius_deg)
        for zj, blist in enumerate(nearby):
            for bi in blist:
                g.add_edge(ids["bridge"][bi], ids["zone"][zj], service="access", dist_deg=0.0)

    return g


def graph_summary(g: nx.DiGraph) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for _, d in g.nodes(data=True):
        counts[d["node_type"]] = counts.get(d["node_type"], 0) + 1
    edge_counts: dict[str, int] = {}
    for _, _, d in g.edges(data=True):
        edge_counts[d["service"]] = edge_counts.get(d["service"], 0) + 1
    return {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(), "node_types": counts, "edge_services": edge_counts}
