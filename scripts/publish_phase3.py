"""Generate Phase 3 publication outputs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.exposure.publish import publish_phase3  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Publish Phase 3 diurnal exposure figures/tables")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/phase3"))
    args = parser.parse_args()
    manifest = publish_phase3(args.output_dir)
    print(manifest)


if __name__ == "__main__":
    main()
