"""Train cross-scenario GNN cascade surrogate."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.cascade.gnn_ensemble import train_cascade_gnn_ensemble  # noqa: E402

if __name__ == "__main__":
    train_cascade_gnn_ensemble()
