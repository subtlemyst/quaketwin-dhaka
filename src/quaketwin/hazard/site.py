"""Vs30-based site response (USGS Global Vs30 Mosaic, Heath et al. 2020).

Amplification follows Borcherdt (1994)-style short-period factors
F_a = (Vref / Vs30)^{m_a}, with the exponent m_a interpolated on bedrock PGA
(nonlinear soil response: stronger shaking -> less linear amplification).
Liquefaction susceptibility is classed from Vs30 (HAZUS-informed thresholds).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from quaketwin.config import ProjectSettings

_VREF = 760.0  # m/s, B/C boundary reference

# (bedrock PGA g, m_a) anchor points, Borcherdt (1994) short-period Fa
_MA_ANCHORS = [(0.1, 0.35), (0.2, 0.25), (0.3, 0.10), (0.4, 0.05)]


def vs30_raster_path() -> Path:
    return ProjectSettings().project_root / "data/raw/vs30/usgs_vs30_dhaka.tif"


@lru_cache(maxsize=1)
def _load_vs30():
    import rasterio

    path = vs30_raster_path()
    if not path.exists():
        return None
    ds = rasterio.open(path)
    arr = ds.read(1).astype(float)
    return ds, arr


def sample_vs30(lons: np.ndarray, lats: np.ndarray) -> np.ndarray | None:
    """Sample Vs30 (m/s) at lon/lat points; None if raster not fetched."""
    loaded = _load_vs30()
    if loaded is None:
        return None
    ds, arr = loaded
    inv = ~ds.transform
    cols_f, rows_f = inv * (np.asarray(lons, dtype=float), np.asarray(lats, dtype=float))
    rows = np.clip(np.floor(rows_f).astype(int), 0, arr.shape[0] - 1)
    cols = np.clip(np.floor(cols_f).astype(int), 0, arr.shape[1] - 1)
    vs30 = arr[rows, cols]
    # Water-body codes (600-603) -> soft-sediment floor typical of river channels
    vs30 = np.where(vs30 >= 600, 180.0, vs30)
    return vs30


def _ma_for_pga(pga_g: float) -> float:
    pgas = [p for p, _ in _MA_ANCHORS]
    mas = [m for _, m in _MA_ANCHORS]
    return float(np.interp(pga_g, pgas, mas))


def vs30_amplification_factor(vs30: float, bedrock_pga_g: float) -> float:
    """Borcherdt-style short-period amplification factor."""
    ma = _ma_for_pga(bedrock_pga_g)
    return float((_VREF / max(vs30, 100.0)) ** ma)


def vs30_liquefaction_susceptibility(vs30: float) -> float:
    """Base susceptibility [0,1] from Vs30 class (HAZUS-informed)."""
    if vs30 < 180:
        return 0.80
    if vs30 < 240:
        return 0.60
    if vs30 < 300:
        return 0.45
    if vs30 < 360:
        return 0.30
    return 0.15
