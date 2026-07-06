"""OSM PBF ingestion for QuakeTwin Dhaka (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import osmium

from quaketwin.config import BoundingBox, get_bbox


def find_osm_pbf(raw_dir: Path | None = None) -> Path:
    """Locate the Bangladesh OSM extract in data/raw."""
    from quaketwin.config import ProjectSettings

    root = raw_dir or ProjectSettings().project_root / "data" / "raw"
    candidates = sorted(root.glob("*.osm.pbf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No .osm.pbf file found in {root}")
    return candidates[0]


def _centroid_in_bbox(w: osmium.osm.Way, bbox: BoundingBox) -> bool:
    lons = [n.lon for n in w.nodes if n.location.valid()]
    lats = [n.lat for n in w.nodes if n.location.valid()]
    if not lons:
        return False
    lon = sum(lons) / len(lons)
    lat = sum(lats) / len(lats)
    return bbox.west <= lon <= bbox.east and bbox.south <= lat <= bbox.north


def _way_polygon(w: osmium.osm.Way) -> list[list[float]] | None:
    coords = [[n.lon, n.lat] for n in w.nodes if n.location.valid()]
    if len(coords) < 3:
        return None
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def _way_linestring(w: osmium.osm.Way) -> list[list[float]] | None:
    coords = [[n.lon, n.lat] for n in w.nodes if n.location.valid()]
    if len(coords) < 2:
        return None
    return coords


def _tags(w: osmium.osm.OSMObject) -> dict[str, str]:
    return {t.k: t.v for t in w.tags}


def _infrastructure_kind(tags: dict[str, str]) -> str | None:
    """Classify an OSM element as a lifeline-infrastructure node type."""
    power = tags.get("power")
    if power in ("substation", "plant", "generator"):
        return f"power_{power}"
    man_made = tags.get("man_made")
    if man_made == "communications_tower":
        return "comm_tower"
    if man_made in ("tower", "mast") and "communication" in tags.get("tower:type", ""):
        return "comm_tower"
    if tags.get("bridge") == "yes" and "highway" in tags:
        return "bridge"
    return None


class _DhakaWayCollector(osmium.SimpleHandler):
    def __init__(self, bbox: BoundingBox, layer: str, progress_every: int = 250_000):
        super().__init__()
        self.bbox = bbox
        self.layer = layer
        self.progress_every = progress_every
        self.ways_seen = 0
        self.features: list[dict[str, Any]] = []
        self.building_tags: dict[str, int] = {}

    def way(self, w: osmium.osm.Way) -> None:
        self.ways_seen += 1
        if self.progress_every and self.ways_seen % self.progress_every == 0:
            print(f"  ... scanned {self.ways_seen:,} ways, kept {len(self.features):,}", flush=True)

        tags = _tags(w)
        if self.layer == "buildings" and "building" not in tags:
            return
        if self.layer == "roads" and "highway" not in tags:
            return
        if self.layer == "hospitals":
            is_health = (
                tags.get("amenity") in ("hospital", "clinic")
                or tags.get("healthcare") == "hospital"
            )
            if not is_health:
                return
        infra_kind = None
        if self.layer == "infrastructure":
            infra_kind = _infrastructure_kind(tags)
            if infra_kind is None:
                return

        if not _centroid_in_bbox(w, self.bbox):
            return

        if self.layer == "infrastructure":
            # Represent infrastructure ways by their centroid point
            lons = [n.lon for n in w.nodes if n.location.valid()]
            lats = [n.lat for n in w.nodes if n.location.valid()]
            if not lons:
                return
            geometry = {
                "type": "Point",
                "coordinates": [sum(lons) / len(lons), sum(lats) / len(lats)],
            }
            self.features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {"osm_id": w.id, "infra_kind": infra_kind, **tags},
                }
            )
            return

        if self.layer == "buildings":
            coords = _way_polygon(w)
            if not coords:
                return
            bt = tags.get("building", "yes")
            self.building_tags[bt] = self.building_tags.get(bt, 0) + 1
            geometry = {"type": "Polygon", "coordinates": [coords]}
        else:
            coords = _way_linestring(w)
            if not coords:
                return
            geometry = {"type": "LineString", "coordinates": coords}

        self.features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "osm_id": w.id,
                    **tags,
                },
            }
        )


class _DhakaNodeCollector(osmium.SimpleHandler):
    """Point features mapped as OSM nodes (hospitals or infrastructure)."""

    def __init__(self, bbox: BoundingBox, layer: str = "hospitals"):
        super().__init__()
        self.bbox = bbox
        self.layer = layer
        self.features: list[dict[str, Any]] = []

    def node(self, n: osmium.osm.Node) -> None:
        if not n.location.valid():
            return
        if not (
            self.bbox.west <= n.location.lon <= self.bbox.east
            and self.bbox.south <= n.location.lat <= self.bbox.north
        ):
            return
        tags = _tags(n)
        props: dict[str, Any]
        if self.layer == "infrastructure":
            infra_kind = _infrastructure_kind(tags)
            if infra_kind is None:
                return
            props = {"osm_id": n.id, "infra_kind": infra_kind, **tags}
        else:
            if tags.get("amenity") not in ("hospital", "clinic") and tags.get("healthcare") != "hospital":
                return
            props = {"osm_id": n.id, **tags}
        self.features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [n.location.lon, n.location.lat]},
                "properties": props,
            }
        )


def validate_pbf(pbf_path: Path) -> dict[str, Any]:
    """Quick validation — opens file without full scan."""
    size_mb = pbf_path.stat().st_size / (1024 * 1024)
    reader = osmium.io.Reader(str(pbf_path))
    reader.close()
    return {
        "path": str(pbf_path),
        "filename": pbf_path.name,
        "size_mb": round(size_mb, 1),
        "format": "OSM PBF",
        "valid": True,
    }


def inspect_osm(pbf_path: Path | None = None, bbox: BoundingBox | None = None) -> dict[str, Any]:
    """Scan PBF and count Dhaka buildings, roads, hospitals (slow on full country)."""
    pbf_path = pbf_path or find_osm_pbf()
    bbox = bbox or get_bbox()
    info = validate_pbf(pbf_path)

    print(f"Scanning {pbf_path.name} ({info['size_mb']} MB) — may take 10–20 min...")

    for layer in ("buildings", "roads", "hospitals"):
        collector = _DhakaWayCollector(bbox, layer)
        collector.apply_file(str(pbf_path), locations=True)
        info[f"{layer}_dhaka"] = len(collector.features)
        if layer == "buildings":
            info["building_tag_top"] = dict(
                sorted(collector.building_tags.items(), key=lambda x: -x[1])[:10]
            )

    node_collector = _DhakaNodeCollector(bbox)
    node_collector.apply_file(str(pbf_path))
    info["hospital_nodes_dhaka"] = len(node_collector.features)
    info["bbox"] = bbox.model_dump()
    return info


def extract_layer(
    layer: str,
    output_path: Path,
    pbf_path: Path | None = None,
    bbox: BoundingBox | None = None,
) -> dict[str, Any]:
    """Extract buildings, roads, hospitals, or infrastructure for Dhaka bbox to GeoJSON."""
    if layer not in {"buildings", "roads", "hospitals", "infrastructure"}:
        raise ValueError("layer must be buildings, roads, hospitals, or infrastructure")

    pbf_path = pbf_path or find_osm_pbf()
    bbox = bbox or get_bbox()

    print(f"Extracting {layer} from {pbf_path.name} ...", flush=True)
    collector = _DhakaWayCollector(bbox, layer)
    collector.apply_file(str(pbf_path), locations=True)
    features = list(collector.features)

    if layer in ("hospitals", "infrastructure"):
        node_collector = _DhakaNodeCollector(bbox, layer)
        node_collector.apply_file(str(pbf_path))
        features.extend(node_collector.features)

    fc = {
        "type": "FeatureCollection",
        "name": f"dhaka_{layer}",
        "metadata": {"source": pbf_path.name, "bbox": bbox.model_dump(), "count": len(features)},
        "features": features,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fc, f)

    result = {"layer": layer, "count": len(features), "output": str(output_path)}
    if layer == "buildings":
        result["building_tag_top"] = dict(
            sorted(collector.building_tags.items(), key=lambda x: -x[1])[:10]
        )
    print(f"Wrote {len(features):,} features -> {output_path}", flush=True)
    return result
