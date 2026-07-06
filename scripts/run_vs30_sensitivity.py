#!/usr/bin/env python3
"""Vs30 class perturbation sensitivity."""

from __future__ import annotations

import json

from quaketwin.analysis.vs30_sensitivity import run_vs30_sensitivity


def main() -> None:
    result = run_vs30_sensitivity()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
