from __future__ import annotations

import numpy as np

from quaketwin.config import BoundingBox


def make_hazard_grid(bbox: BoundingBox, cell_size_deg: float = 0.0045) -> list[dict]:
    """
    Regular lon/lat grid over study area bbox.

    cell_size_deg ≈ 0.0045° (~500 m at 23.8°N) — configurable in dhaka.yaml.
    """
    lons = np.arange(bbox.west, bbox.east + cell_size_deg / 2, cell_size_deg)
    lats = np.arange(bbox.south, bbox.north + cell_size_deg / 2, cell_size_deg)

    cells = []
    for lat in lats:
        for lon in lons:
            cells.append({"lon": float(lon), "lat": float(lat)})
    return cells
