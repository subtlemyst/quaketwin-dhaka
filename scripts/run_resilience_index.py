"""Compute Earthquake Resilience Index (ERI)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.resilience.pipeline import compute_resilience_index  # noqa: E402

if __name__ == "__main__":
    compute_resilience_index()
