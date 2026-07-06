"""Build enriched building profiles (hazard + population + collapse risk)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.data.enrich import build_building_profiles  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Phase 2: enrich Dhaka buildings with hazard and population")
    parser.add_argument(
        "--format",
        choices=["gpkg", "geojson"],
        default="gpkg",
        help="Output format (gpkg recommended for 700k+ buildings)",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    build_building_profiles(output_path=args.output, output_format=args.format)


if __name__ == "__main__":
    main()
