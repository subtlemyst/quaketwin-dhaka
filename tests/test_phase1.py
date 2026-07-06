"""Phase 0–1 tests for QuakeTwin Dhaka thesis scaffold."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quaketwin.config import get_bbox, load_config
from quaketwin.hazard.ground_motion import compute_ground_motion_grid, pga_to_mmi
from quaketwin.hazard.scenario import load_default_scenario
from quaketwin.pipeline import run_phase1_hazard
from quaketwin.schema.inventory import load_data_inventory


def test_config_loads():
    cfg = load_config()
    assert "study_area" in cfg
    assert cfg["default_scenario"]["magnitude"] == 7.2


def test_bbox_valid():
    bbox = get_bbox()
    assert bbox.west < bbox.east
    assert bbox.south < bbox.north


def test_default_scenario():
    s = load_default_scenario()
    assert s.magnitude == 7.2
    assert s.fault_name == "Dauki Fault Zone"


def test_pga_decreases_with_distance():
    scenario = load_default_scenario()
    near = {"lon": 90.50, "lat": 23.90}
    far = {"lon": 90.32, "lat": 23.68}
    result = compute_ground_motion_grid([near, far], scenario)
    assert result[0]["pga_g"] > result[1]["pga_g"]


def test_dhaka_pga_realistic_range():
    """Bedrock PGA at Greater Dhaka should be plausible for Mw 7.2 at ~150-200 km."""
    scenario = load_default_scenario()
    dhaka = {"lon": 90.41, "lat": 23.81}
    pga = compute_ground_motion_grid([dhaka], scenario)[0]["pga_g"]
    assert 0.04 <= pga <= 0.35, f"PGA {pga}g outside expected range for Dhaka"


def test_mmi_range():
    assert 1.0 <= pga_to_mmi(0.01) <= 12.0
    assert pga_to_mmi(0.5) > pga_to_mmi(0.05)


def test_phase1_pipeline_output():
    fc = run_phase1_hazard()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) > 100
    props = fc["features"][0]["properties"]
    assert "pga_g" in props
    assert "liquefaction_index" in props
    assert 0 <= props["liquefaction_index"] <= 1


def test_data_inventory():
    records = load_data_inventory()
    assert len(records) >= 5
    layers = {r.layer_name for r in records}
    assert "buildings" in layers
    assert "roads" in layers
