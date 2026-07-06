"""Train the Phase 5 GNN surrogate on Monte Carlo cascade outputs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.cascade.gnn import train_cascade_gnn  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Train GNN cascade surrogate")
    parser.add_argument("--period", default="midday")
    parser.add_argument("--epochs", type=int, default=400)
    parser.add_argument("--hidden", type=int, default=32)
    args = parser.parse_args()
    train_cascade_gnn(period=args.period, epochs=args.epochs, hidden=args.hidden)


if __name__ == "__main__":
    main()
