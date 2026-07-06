"""Extract Dhaka buildings, roads, or hospitals from OSM PBF to GeoJSON."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.data.osm import extract_layer, find_osm_pbf  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Extract Dhaka OSM layers to GeoJSON")
    parser.add_argument(
        "--layer",
        choices=["buildings", "roads", "hospitals", "infrastructure", "all"],
        default="buildings",
    )
    parser.add_argument("--pbf", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
    )
    args = parser.parse_args()

    pbf = args.pbf or find_osm_pbf()
    layers = (
        ["buildings", "roads", "hospitals", "infrastructure"]
        if args.layer == "all"
        else [args.layer]
    )

    for layer in layers:
        out = args.output_dir / f"dhaka_{layer}.geojson"
        extract_layer(layer, out, pbf_path=pbf)


if __name__ == "__main__":
    main()
