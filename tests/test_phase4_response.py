"""Phase 4 smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.response.pipeline import load_response_config


def test_response_config_loads():
    cfg = load_response_config()
    assert cfg["default_period"] == "midday"
    assert "hospital_capacity" in cfg
