"""Map OSM building tags to structural / occupancy features."""

from __future__ import annotations

import re

# OSM building=* -> normalized construction class for fragility model
_CONSTRUCTION_MAP: dict[str, str] = {
    "residential": "residential",
    "house": "residential",
    "apartments": "rc",
    "commercial": "commercial",
    "industrial": "industrial",
    "school": "institutional",
    "university": "institutional",
    "hospital": "institutional",
    "mosque": "institutional",
    "church": "institutional",
    "retail": "commercial",
    "office": "rc",
    "warehouse": "industrial",
    "shed": "informal",
    "hut": "informal",
    "construction": "unknown",
    "yes": "unknown",
    "brick": "masonry",
    "masonry": "masonry",
    "concrete": "rc",
    "steel": "rc",
    "wood": "wood",
    "metal": "informal",
    "tin": "informal",
}

_DEFAULT_HEIGHT_M: dict[str, float] = {
    "residential": 6.0,
    "rc": 12.0,
    "commercial": 10.0,
    "industrial": 8.0,
    "institutional": 8.0,
    "masonry": 6.0,
    "wood": 4.0,
    "informal": 3.0,
    "unknown": 6.0,
}

_OCCUPANCY_MAP: dict[str, str] = {
    "residential": "residential",
    "house": "residential",
    "apartments": "residential",
    "commercial": "commercial",
    "industrial": "industrial",
    "school": "education",
    "university": "education",
    "hospital": "healthcare",
    "mosque": "assembly",
    "church": "assembly",
    "retail": "commercial",
    "office": "commercial",
    "warehouse": "industrial",
    "shed": "storage",
    "yes": "residential",
}


def normalize_construction_type(osm_building: str | None) -> str:
    if not osm_building:
        return "unknown"
    key = osm_building.strip().lower()
    return _CONSTRUCTION_MAP.get(key, "unknown")


def infer_occupancy(osm_building: str | None, amenity: str | None = None) -> str:
    if amenity:
        am = amenity.lower()
        if am in ("school", "college", "university"):
            return "education"
        if am in ("hospital", "clinic"):
            return "healthcare"
        if am in ("place_of_worship",):
            return "assembly"
    if not osm_building:
        return "residential"
    return _OCCUPANCY_MAP.get(osm_building.strip().lower(), "residential")


def infer_height_m(
    construction_type: str,
    levels: str | float | None = None,
    height: str | float | None = None,
) -> float:
    if height is not None:
        try:
            h = str(height).lower().replace("m", "").strip()
            return float(h)
        except ValueError:
            pass
    if levels is not None:
        try:
            return float(str(levels)) * 3.0
        except ValueError:
            pass
    return _DEFAULT_HEIGHT_M.get(construction_type, 6.0)


def parse_osm_properties(props: dict) -> dict:
    """Extract normalized building attributes from raw OSM feature properties."""
    osm_building = props.get("building")
    construction = normalize_construction_type(osm_building)
    return {
        "building_id": int(props.get("osm_id", 0)),
        "construction_type": construction,
        "height_m": infer_height_m(
            construction,
            props.get("building:levels"),
            props.get("height"),
        ),
        "occupancy_type": infer_occupancy(osm_building, props.get("amenity")),
        "osm_building_tag": osm_building,
    }
