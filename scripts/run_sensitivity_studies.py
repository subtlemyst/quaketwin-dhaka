"""Run all one-at-a-time sensitivity studies for the manuscript."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.analysis.sensitivity import run_all_sensitivity_studies  # noqa: E402


def main() -> None:
    out = run_all_sensitivity_studies()
    print(json.dumps(out, indent=2), flush=True)


if __name__ == "__main__":
    main()
