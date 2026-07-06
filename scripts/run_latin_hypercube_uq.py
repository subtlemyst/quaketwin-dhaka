#!/usr/bin/env python3
"""Latin Hypercube uncertainty propagation (citywide CIs)."""

from __future__ import annotations

import argparse
import json

from quaketwin.analysis.uq import run_latin_hypercube_uq


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("-n", "--samples", type=int, default=128)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    result = run_latin_hypercube_uq(n_samples=args.samples, seed=args.seed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
