"""Generate Phase 5 publication figures and tables."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.cascade.publish import publish_phase5  # noqa: E402

if __name__ == "__main__":
    publish_phase5()
