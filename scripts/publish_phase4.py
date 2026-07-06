"""Generate Phase 4 publication outputs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.response.publish import publish_phase4  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Publish Phase 4 response figures/tables")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/phase4"))
    args = parser.parse_args()
    print(publish_phase4(args.output_dir))


if __name__ == "__main__":
    main()
