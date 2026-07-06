"""Merge Google Open Buildings height estimates into building profiles."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from quaketwin.config import ProjectSettings


def heights_parquet_path() -> Path:
    root = ProjectSettings().project_root / "data/raw/open_buildings"
    pq = root / "dhaka_heights.parquet"
    if pq.exists():
        return pq
    return root / "dhaka_heights.csv"


@lru_cache(maxsize=1)
def _load_heights() -> pd.DataFrame | None:
    path = heights_parquet_path()
    if not path.exists():
        return None
    if path.suffix == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_parquet(path)
    if not {"lon", "lat", "height_m"}.issubset(df.columns):
        return None
    return df


def merge_open_buildings_heights(
    lons: np.ndarray,
    lats: np.ndarray,
    existing_height_m: np.ndarray,
    max_snap_deg: float = 0.00015,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (height_m, height_source) where source is 'open_buildings' or 'osm_default'.

    Nearest Open Buildings point within ~15 m replaces OSM height when taller/more informative.
    """
    heights = _load_heights()
    out = existing_height_m.astype(float).copy()
    source = np.array(["osm_default"] * len(out), dtype=object)
    if heights is None or len(heights) == 0:
        return out, source

    tree = cKDTree(heights[["lon", "lat"]].to_numpy())
    q = np.column_stack([lons, lats])
    dist, idx = tree.query(q, k=1)
    dist_deg = dist  # approximate; bbox is small
    mask = dist_deg <= max_snap_deg
    ob_h = heights["height_m"].to_numpy()[idx]
    use = mask & (ob_h > 3.0)
    out[use] = np.maximum(out[use], ob_h[use])
    source[use] = "open_buildings"
    out = np.clip(out, 3.0, 120.0)
    return out, source
