#!/usr/bin/env python3
"""Compare manual vs entropy ERI weights."""

from __future__ import annotations

import json
from pathlib import Path

from quaketwin.config import ProjectSettings
from quaketwin.resilience.pipeline import compare_eri_weighting_schemes


def main() -> None:
    result = compare_eri_weighting_schemes()
    out = ProjectSettings().project_root / "outputs/eri_weight_comparison.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
