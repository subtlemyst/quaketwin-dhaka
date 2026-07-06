"""Inspect OSM PBF file and count Dhaka features."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.data.osm import find_osm_pbf, inspect_osm, validate_pbf  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Validate OSM PBF and inspect Dhaka coverage")
    parser.add_argument("--pbf", type=Path, default=None, help="Path to .osm.pbf")
    parser.add_argument("--quick", action="store_true", help="Validate file only (fast)")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report")
    args = parser.parse_args()

    pbf = args.pbf or find_osm_pbf()
    if args.quick:
        report = validate_pbf(pbf)
    else:
        report = inspect_osm(pbf)

    print(json.dumps(report, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
