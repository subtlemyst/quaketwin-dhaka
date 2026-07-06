#!/usr/bin/env python3
"""External validation: literature envelopes and historical analog replay."""

from __future__ import annotations

import json

from quaketwin.analysis.external_validation import run_external_validation


def main() -> None:
    result = run_external_validation()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
