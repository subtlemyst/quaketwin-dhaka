"""Generate Phase 2 thesis publication bundle."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.publish import publish_phase2  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Phase 2 publication outputs: validation, tables, figures"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/phase2"),
    )
    parser.add_argument("--profiles", type=Path, default=None)
    args = parser.parse_args()
    publish_phase2(out_dir=args.output_dir, profiles_path=args.profiles)


if __name__ == "__main__":
    main()
