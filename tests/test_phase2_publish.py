"""Phase 2 publication tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.publish.validation import validate_hazard_gmpe


def test_gmpe_benchmark_passes():
    result = validate_hazard_gmpe()
    assert all(c["pass"] for c in result["benchmark_checks"])


def test_dhaka_pga_in_range():
    result = validate_hazard_gmpe()
    mean_pga = result["model_pga_bedrock"]["mean"]
    assert 0.06 <= mean_pga <= 0.25
