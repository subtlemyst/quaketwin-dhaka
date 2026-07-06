from __future__ import annotations

import math

from quaketwin.config import get_bbox, load_config


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in kilometers (WGS84 spherical approximation)."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def assign_soil_zone(lon: float, lat: float, config: dict | None = None) -> str:
    """
    Proxy soil zoning for Dhaka basin until geotechnical rasters are ingested.

    Zones follow config/dhaka.yaml soil_zones keys. Pattern is illustrative —
    document and replace with borehole-validated polygons in Phase 0 data work.
    """
    cfg = config or load_config()
    zones = cfg["soil_zones"]

    # Eastern lowlands / Buriganga fringe → marsh organic
    if lon > 90.44 and lat < 23.78:
        return "marsh_organic"
    # Central business / old town soft alluvium
    if 90.38 <= lon <= 90.44 and 23.78 <= lat <= 23.88:
        return "holocene_alluvium"
    # Northern terrace
    if lat > 23.88:
        return "pleistocene_terrace"
    # Western fill / expansion areas
    if lon < 90.38:
        return "engineered_fill"
    return "holocene_alluvium"


def soil_zone_properties(zone_code: str, config: dict | None = None) -> dict:
    cfg = config or load_config()
    return cfg["soil_zones"][zone_code]


def study_area_summary() -> dict:
    cfg = load_config()
    bbox = get_bbox(cfg)
    return {
        "name": cfg["study_area"]["name"],
        "bbox": bbox.model_dump(),
        "center": cfg["study_area"]["center"],
        "crs": cfg["study_area"]["crs"],
    }
