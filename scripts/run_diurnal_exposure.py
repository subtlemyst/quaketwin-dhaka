"""Run Phase 3 diurnal population exposure pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.exposure.pipeline import run_diurnal_exposure  # noqa: E402


def main() -> None:
    run_diurnal_exposure()


if __name__ == "__main__":
    main()
