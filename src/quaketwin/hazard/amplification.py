from __future__ import annotations

import numpy as np

from quaketwin.geo.dhaka import assign_soil_zone, soil_zone_properties
from quaketwin.hazard.site import sample_vs30, vs30_amplification_factor


def _site_class(vs30: float) -> str:
    if vs30 < 180:
        return "E"
    if vs30 < 360:
        return "D"
    if vs30 < 760:
        return "C"
    return "B"


def apply_soil_amplification(shaking_grid: list[dict]) -> list[dict]:
    """
    Apply site amplification to bedrock PGA.

    Primary path: USGS Global Vs30 Mosaic (Heath et al. 2020) with
    Borcherdt-style short-period factors. Fallback (raster not fetched):
    zone-level multipliers from config/dhaka.yaml.
    """
    lons = np.array([c["lon"] for c in shaking_grid])
    lats = np.array([c["lat"] for c in shaking_grid])
    vs30 = sample_vs30(lons, lats)

    amplified = []
    for i, cell in enumerate(shaking_grid):
        zone = assign_soil_zone(cell["lon"], cell["lat"])
        if vs30 is not None:
            v = float(vs30[i])
            factor = vs30_amplification_factor(v, cell["pga_g"])
            site_code = _site_class(v)
            extra = {"vs30": round(v, 1), "site_method": "usgs_vs30_borcherdt"}
        else:
            props = soil_zone_properties(zone)
            factor = props["amplification_factor"]
            site_code = props["code"]
            extra = {"site_method": "proxy_zones"}
        amp_pga = cell["pga_g"] * factor
        amplified.append(
            {
                **cell,
                "soil_zone_code": site_code,
                "soil_zone": zone,
                "amplification_factor": round(factor, 3),
                "amplified_pga_g": amp_pga,
                "amplified_mmi": min(12.0, cell["mmi"] + (factor - 1.0) * 1.5),
                **extra,
            }
        )
    return amplified
