"""Run the Phase 5 infrastructure cascade Monte Carlo simulation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.cascade.simulate import run_cascade  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Phase 5 infrastructure cascade simulation")
    parser.add_argument("--period", default="midday",
                        choices=["midnight", "morning_commute", "midday", "evening"])
    args = parser.parse_args()
    run_cascade(period=args.period)


if __name__ == "__main__":
    main()
