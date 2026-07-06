"""Phase 2 publication bundle — validation, tables, figures."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quaketwin.config import ProjectSettings
from quaketwin.publish.figures import generate_all_figures
from quaketwin.publish.tables import export_tables
from quaketwin.publish.validation import validate_building_risk, validate_hazard_gmpe


def publish_phase2(
    out_dir: Path | None = None,
    profiles_path: Path | None = None,
) -> dict[str, Any]:
    """
    Generate all Phase 2 thesis outputs:

    - Validation report (GMPE + building risk)
    - CSV tables (T6.1–T6.6)
    - PNG figures (F5.1–F5.4, F6.1–F6.3)
    - Manifest JSON
    """
    root = ProjectSettings().project_root.resolve()
    out_dir = (out_dir or root / "outputs" / "phase2").resolve()
    figures_dir = out_dir / "figures"
    tables_dir = out_dir / "tables"
    profiles_path = profiles_path or root / "data/processed/dhaka_building_profiles.gpkg"

    print("Validating hazard GMPE...", flush=True)
    hazard_validation = validate_hazard_gmpe()

    print("Validating building risk...", flush=True)
    building_validation = validate_building_risk(profiles_path)

    print("Exporting tables...", flush=True)
    table_paths = export_tables(tables_dir, profiles_path)

    print("Generating figures...", flush=True)
    figure_paths = generate_all_figures(figures_dir, profiles_path)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": "dhaka_mw72_dauki",
        "phase": 2,
        "primary_collapse_model": "fragility",
        "ml_note": (
            "XGBoost collapse_probability_ml is optional sensitivity analysis; "
            "thesis maps use fragility-based collapse_probability."
        ),
        "hazard_validation": hazard_validation,
        "building_validation": building_validation,
        "tables": [str(p.relative_to(root)) for p in table_paths],
        "figures": [str(p.relative_to(root)) for p in figure_paths],
        "publishable_checklist": {
            "hazard_gmpe_within_literature_range": all(
                c["pass"] for c in hazard_validation["benchmark_checks"]
            ),
            "buildings_processed": building_validation["buildings"] >= 500_000,
            "risk_spread_realistic": 0.05 < building_validation["mean_collapse_p"] < 0.95,
            "figures_generated": len(figure_paths) >= 6,
            "tables_generated": len(table_paths) >= 5,
        },
    }

    manifest_path = out_dir / "publish_manifest.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps(manifest["publishable_checklist"], indent=2), flush=True)
    print(f"Manifest: {manifest_path}", flush=True)
    return manifest
