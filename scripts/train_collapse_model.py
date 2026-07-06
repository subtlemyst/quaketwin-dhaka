"""Train XGBoost collapse probability model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.risk.train import train_collapse_model  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Train XGBoost collapse model (Phase 2)")
    parser.add_argument("--sample", type=int, default=100_000, help="Training sample size")
    parser.add_argument("--profiles", type=Path, default=None)
    args = parser.parse_args()
    train_collapse_model(profiles_path=args.profiles, sample_n=args.sample)


if __name__ == "__main__":
    main()
