"""Verify all Phase 0-2 data files are present and valid."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.config import get_bbox
from quaketwin.data.osm import validate_pbf

EXPECTED = {
    "osm": ROOT / "data/raw/bangladesh-260630.osm.pbf",
    "worldpop": ROOT / "data/raw/population/worldpop_bgd_2020.tif",
    "hazard": ROOT / "data/processed/hazard_mw72_dauki.geojson",
    "buildings": ROOT / "data/processed/dhaka_buildings.geojson",
    "profiles": ROOT / "data/processed/dhaka_building_profiles.gpkg",
    "roads": ROOT / "data/processed/dhaka_roads.geojson",
    "hospitals": ROOT / "data/processed/dhaka_hospitals.geojson",
}


def main() -> None:
    bbox = get_bbox()
    print("=== QuakeTwin Data Inventory ===\n")
    print(f"Project root: {ROOT}")
    print(f"Dhaka bbox: {bbox.model_dump()}\n")

    # OSM
    pbf = EXPECTED["osm"]
    if pbf.exists():
        info = validate_pbf(pbf)
        print(f"[OK] OSM PBF")
        print(f"     {pbf.relative_to(ROOT)}")
        print(f"     {info['size_mb']} MB, valid PBF\n")
    else:
        print(f"[MISSING] OSM PBF at {pbf.relative_to(ROOT)}\n")

    # WorldPop
    pop = EXPECTED["worldpop"]
    if pop.exists():
        hdr = pop.read_bytes()[:2]
        ok = hdr in (b"II", b"MM")
        print(f"[{'OK' if ok else 'BAD'}] WorldPop raster")
        print(f"     {pop.relative_to(ROOT)}")
        print(f"     {pop.stat().st_size / 1024 / 1024:.1f} MB")
        try:
            import rasterio
            from rasterio.windows import from_bounds

            b = bbox.as_tuple
            with rasterio.open(pop) as ds:
                covers = (
                    ds.bounds.left <= b[0]
                    and ds.bounds.right >= b[2]
                    and ds.bounds.bottom <= b[1]
                    and ds.bounds.top >= b[3]
                )
                win = from_bounds(*b, transform=ds.transform)
                data = ds.read(1, window=win, masked=True)
                print(f"     covers Dhaka: {covers}, pop sum ~{float(data.sum()):,.0f}\n")
        except ImportError:
            print("     (install rasterio for coverage check)\n")
    else:
        print(f"[MISSING] WorldPop at {pop.relative_to(ROOT)}\n")

    # Hazard
    hazard = EXPECTED["hazard"]
    if hazard.exists():
        fc = json.loads(hazard.read_text(encoding="utf-8"))
        n = len(fc.get("features", []))
        print(f"[OK] Phase 1 hazard GeoJSON")
        print(f"     {hazard.relative_to(ROOT)}")
        print(f"     {n:,} grid cells\n")
    else:
        print(f"[MISSING] Hazard at {hazard.relative_to(ROOT)}\n")

    # Processed OSM layers
    profiles = EXPECTED.get("profiles")
    if profiles and profiles.exists():
        mb = profiles.stat().st_size / 1024 / 1024
        print(f"[OK] building profiles (Phase 2)")
        print(f"     {profiles.relative_to(ROOT)} — {mb:.1f} MB\n")

    for key in ("buildings", "roads", "hospitals"):
        path = EXPECTED[key]
        if path.exists():
            if path.suffix == ".geojson":
                fc = json.loads(path.read_text(encoding="utf-8"))
                count = len(fc.get("features", []))
            else:
                count = "?"
            mb = path.stat().st_size / 1024 / 1024
            print(f"[OK] {key}")
            print(f"     {path.relative_to(ROOT)} — {count:,} features, {mb:.1f} MB\n")
        else:
            print(f"[PENDING] {key}")
            print(f"     {path.relative_to(ROOT)} — run extract_dhaka_osm.py\n")

    # Wrong location warning
    wrong = Path.home() / "data" / "raw"
    if wrong.exists() and wrong.resolve() != (ROOT / "data" / "raw").resolve():
        extra = list(wrong.rglob("*"))
        if any(p.is_file() for p in extra):
            print(f"[WARN] Data also found outside project: {wrong}")
            print("       Use earthquake/data/raw/ only.\n")


if __name__ == "__main__":
    main()
