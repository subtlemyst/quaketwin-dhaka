"""Run Phase 4 response model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.response.pipeline import run_response_model  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run Phase 4 hospital overload and rescue priority model")
    parser.add_argument("--period", type=str, default=None, help="midnight, morning_commute, midday, evening")
    args = parser.parse_args()
    run_response_model(period=args.period)


if __name__ == "__main__":
    main()
