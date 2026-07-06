from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as script without install
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.pipeline import run_phase1_hazard  # noqa: E402
from quaketwin.hazard.scenario import EarthquakeScenario, scenario_from_fault  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run Phase 1 hazard pipeline for QuakeTwin Dhaka")
    parser.add_argument("--magnitude", type=float, default=None, help="Earthquake magnitude (Mw)")
    parser.add_argument("--fault", choices=["dauki", "madhupur"], default="dauki")
    parser.add_argument("--scenario-id", type=str, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/hazard_mw72_dauki.geojson"),
        help="Output GeoJSON path",
    )
    args = parser.parse_args()

    if args.magnitude:
        scenario = scenario_from_fault(args.fault, args.magnitude, args.scenario_id)
    else:
        scenario = None

    result = run_phase1_hazard(scenario=scenario)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    meta = result["metadata"]
    print(f"Scenario: {meta['scenario']['id']}")
    print(f"Cells: {meta['cell_count']}")
    print(f"Written: {args.output}")


if __name__ == "__main__":
    main()
