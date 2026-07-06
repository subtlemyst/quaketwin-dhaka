"""Run multi-scenario hazard + cascade ensemble."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.cascade.ensemble import run_scenario_ensemble  # noqa: E402

if __name__ == "__main__":
    run_scenario_ensemble()
