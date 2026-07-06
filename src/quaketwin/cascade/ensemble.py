"""Multi-scenario hazard + cascade ensemble (Phase 5 upgrade)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from quaketwin.config import ProjectSettings
from quaketwin.hazard.scenario import scenario_from_fault
from quaketwin.pipeline import run_phase1_hazard
from quaketwin.cascade.simulate import run_cascade


def load_scenarios_config() -> dict[str, Any]:
    path = ProjectSettings().project_root / "config/scenarios.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def hazard_path_for(scenario_id: str) -> Path:
    root = ProjectSettings().project_root
    return root / "data/processed" / f"hazard_{scenario_id}.geojson"


def run_scenario_ensemble(period: str = "midday") -> dict[str, Any]:
    """Generate hazard layers and cascade MC outputs for all train/test scenarios."""
    cfg = load_scenarios_config()
    root = ProjectSettings().project_root
    processed = root / "data/processed"
    n_iter = int(cfg.get("monte_carlo_iterations", 300))

    all_scenarios = cfg["train_scenarios"] + cfg["test_scenarios"]
    summaries: list[dict[str, Any]] = []

    for spec in all_scenarios:
        sid = spec["id"]
        print(f"\n=== Scenario {sid} ===", flush=True)
        scenario = scenario_from_fault(spec["fault"], float(spec["magnitude"]), sid)
        hazard_out = hazard_path_for(sid)
        hazard_out.parent.mkdir(parents=True, exist_ok=True)
        fc = run_phase1_hazard(scenario=scenario)
        hazard_out.write_text(json.dumps(fc, indent=2), encoding="utf-8")
        print(f"Hazard written: {hazard_out}", flush=True)

        summary = run_cascade(
            period=period,
            hazard_path=hazard_out,
            scenario_id=sid,
            n_iterations=n_iter,
        )
        summaries.append(summary)

    # Backward-compatible aliases for default thesis scenario
    baseline = "dhaka_mw72_dauki"
    for src, dst in [
        (f"cascade_nodes_{baseline}.gpkg", "cascade_nodes_phase5.gpkg"),
        (f"cascade_zones_{baseline}.gpkg", "cascade_zones_phase5.gpkg"),
        (f"cascade_{baseline}_summary.json", "cascade_phase5_summary.json"),
        (f"hazard_{baseline}.geojson", "hazard_mw72_dauki.geojson"),
    ]:
        s, d = processed / src, processed / dst
        if s.exists():
            shutil.copy2(s, d)

    manifest = {
        "period": period,
        "monte_carlo_iterations": n_iter,
        "train_scenarios": [s["id"] for s in cfg["train_scenarios"]],
        "test_scenarios": [s["id"] for s in cfg["test_scenarios"]],
        "summaries": summaries,
    }
    out = processed / "cascade_ensemble_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)
    return manifest
