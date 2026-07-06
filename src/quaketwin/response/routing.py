"""Road-network travel-time estimation (Phase 4 upgrade)."""

from __future__ import annotations

from typing import Any

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point


def _endpoint_coords(geom) -> tuple[tuple[float, float], tuple[float, float]]:
    if geom.geom_type == "LineString":
        coords = list(geom.coords)
    else:
        coords = list(geom.geoms[0].coords) if len(geom.geoms) else [(0, 0), (0, 0)]
    return coords[0], coords[-1]


_ROUTING_CLASSES = ("motorway", "trunk", "primary", "secondary", "tertiary", "residential")


def build_routable_graph(
    roads: gpd.GeoDataFrame,
    speed_kmh: dict[str, float],
    major_only: bool = True,
) -> tuple[nx.Graph, gpd.GeoDataFrame, np.ndarray]:
    """
    Build an undirected routable graph from OSM roads in EPSG:3857.

    Returns graph, node GeoDataFrame (x,y in 3857), and node coordinate array.
    """
    r = roads.copy()
    if major_only:
        keep = set(_ROUTING_CLASSES) & set(speed_kmh.keys())
        r = r[r["highway"].fillna("unclassified").isin(keep)]
    r = r.to_crs(3857)

    node_map: dict[tuple[float, float], int] = {}
    node_rows: list[dict] = []

    def _node_id(x: float, y: float) -> int:
        key = (round(x, 1), round(y, 1))
        if key not in node_map:
            node_map[key] = len(node_rows)
            node_rows.append({"x": key[0], "y": key[1]})
        return node_map[key]

    g = nx.Graph()
    for _, row in r.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        (x0, y0), (x1, y1) = _endpoint_coords(geom)
        u, v = _node_id(x0, y0), _node_id(x1, y1)
        if u == v:
            continue
        speed = float(speed_kmh.get(str(row.get("highway") or "unclassified"), 10.0))
        length_m = geom.length
        minutes = (length_m / 1000.0) / max(speed, 1.0) * 60.0
        if g.has_edge(u, v):
            if minutes < g[u][v]["weight"]:
                g[u][v]["weight"] = minutes
        else:
            g.add_edge(u, v, weight=minutes, length_m=length_m)

    nodes = gpd.GeoDataFrame(node_rows)
    coords = nodes[["x", "y"]].to_numpy()
    return g, nodes, coords


def network_travel_minutes(
    building_lon: np.ndarray,
    building_lat: np.ndarray,
    hospital_lon: np.ndarray,
    hospital_lat: np.ndarray,
    roads: gpd.GeoDataFrame,
    speed_kmh: dict[str, float],
) -> np.ndarray:
    """
    Multi-source shortest-path travel time (minutes) from each building to nearest hospital.

    Falls back to NaN when graph routing fails; caller should use straight-line proxy.
    """
    if len(roads) == 0 or len(hospital_lon) == 0:
        return np.full(len(building_lon), np.nan)

    g, nodes, node_coords = build_routable_graph(roads, speed_kmh)
    if g.number_of_nodes() == 0:
        return np.full(len(building_lon), np.nan)

    tree = cKDTree(node_coords)
    b3857 = gpd.GeoSeries(
        [Point(xy) for xy in zip(building_lon, building_lat)], crs="EPSG:4326"
    ).to_crs(3857)
    h3857 = gpd.GeoSeries(
        [Point(xy) for xy in zip(hospital_lon, hospital_lat)], crs="EPSG:4326"
    ).to_crs(3857)

    _, b_idx = tree.query(np.column_stack([b3857.x, b3857.y]))
    _, h_idx = tree.query(np.column_stack([h3857.x, h3857.y]))
    sources = {int(i) for i in np.unique(h_idx)}

    try:
        dist = nx.multi_source_dijkstra_path_length(g, sources, weight="weight")
    except nx.NetworkXError:
        return np.full(len(building_lon), np.nan)

    base = np.array([dist.get(int(i), np.inf) for i in b_idx], dtype=float)
    # Last-mile penalty: building snap distance at 12 km/h
    snap_m = np.hypot(
        b3857.x.to_numpy() - node_coords[b_idx, 0],
        b3857.y.to_numpy() - node_coords[b_idx, 1],
    )
    last_mile = (snap_m / 1000.0) / 12.0 * 60.0
    total = base + last_mile
    total = np.where(np.isfinite(total), total, np.nan)
    return total


def travel_minutes_to_assigned_hospitals(
    building_lon: np.ndarray,
    building_lat: np.ndarray,
    assigned_hosp_lon: np.ndarray,
    assigned_hosp_lat: np.ndarray,
    roads: gpd.GeoDataFrame,
    speed_kmh: dict[str, float],
) -> np.ndarray:
    """Network travel time (minutes) from each building to its assigned hospital."""
    n = len(building_lon)
    if len(roads) == 0:
        return np.full(n, np.nan)

    g, nodes, node_coords = build_routable_graph(roads, speed_kmh)
    if g.number_of_nodes() == 0:
        return np.full(n, np.nan)

    tree = cKDTree(node_coords)
    b3857 = gpd.GeoSeries(
        [Point(xy) for xy in zip(building_lon, building_lat)], crs="EPSG:4326"
    ).to_crs(3857)
    h3857 = gpd.GeoSeries(
        [Point(xy) for xy in zip(assigned_hosp_lon, assigned_hosp_lat)], crs="EPSG:4326"
    ).to_crs(3857)

    b_xy = np.column_stack([b3857.x.to_numpy(), b3857.y.to_numpy()])
    h_xy = np.column_stack([h3857.x.to_numpy(), h3857.y.to_numpy()])
    _, b_idx = tree.query(b_xy)
    _, h_idx = tree.query(h_xy)

    snap_m = np.hypot(b_xy[:, 0] - node_coords[b_idx, 0], b_xy[:, 1] - node_coords[b_idx, 1])
    last_mile = (snap_m / 1000.0) / 12.0 * 60.0

    out = np.full(n, np.nan, dtype=float)
    unique_h = np.unique(h_idx)
    for i, h_node in enumerate(unique_h):
        mask = h_idx == h_node
        try:
            lengths = nx.single_source_dijkstra_path_length(g, int(h_node), weight="weight")
        except nx.NetworkXError:
            continue
        b_nodes = b_idx[mask]
        base = np.array([lengths.get(int(j), np.inf) for j in b_nodes], dtype=float)
        out[mask] = base + last_mile[mask]
        if (i + 1) % 100 == 0:
            print(f"    routing hospitals {i + 1}/{len(unique_h)}", flush=True)
    return out
