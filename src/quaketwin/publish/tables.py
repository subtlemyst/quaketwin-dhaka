"""Export thesis tables for Phase 2 publication."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from quaketwin.publish.validation import validate_building_risk, validate_hazard_gmpe


def export_tables(out_dir: Path, profiles_path: Path | None = None) -> list[Path]:
    """Write CSV tables T6.x for thesis."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    hazard_val = validate_hazard_gmpe()
    bench_rows = []
    for check in hazard_val["benchmark_checks"]:
        bench_rows.append(
            {
                "benchmark_id": check["benchmark"],
                "description": check["description"],
                "expected_min": check["expected_range"][0],
                "expected_max": check["expected_range"][1],
                "model_value": check["model_mean"],
                "pass": check["pass"],
                "reference": check["reference"],
            }
        )
    t61 = out_dir / "T6_1_gmpe_validation.csv"
    pd.DataFrame(bench_rows).to_csv(t61, index=False)
    written.append(t61)

    t62 = out_dir / "T6_2_hazard_summary.csv"
    pd.DataFrame(
        [
            {"metric": "epicenter_to_dhaka_km", "value": hazard_val["epicenter_to_dhaka_center_km"]},
            {"metric": "pga_bedrock_min", "value": hazard_val["model_pga_bedrock"]["min"]},
            {"metric": "pga_bedrock_max", "value": hazard_val["model_pga_bedrock"]["max"]},
            {"metric": "pga_bedrock_mean", "value": hazard_val["model_pga_bedrock"]["mean"]},
            {"metric": "pga_amplified_mean", "value": hazard_val["model_pga_amplified"]["mean"]},
            {"metric": "mmi_mean", "value": hazard_val["model_mmi"]["mean"]},
        ]
    ).to_csv(t62, index=False)
    written.append(t62)

    building_val = validate_building_risk(profiles_path)
    t63 = out_dir / "T6_3_risk_by_construction_type.csv"
    pd.DataFrame(building_val["by_construction_type"]).to_csv(t63, index=False)
    written.append(t63)

    t64 = out_dir / "T6_4_risk_class_summary.csv"
    pd.DataFrame(
        [{"risk_class": k, "building_count": v} for k, v in building_val["risk_class_counts"].items()]
    ).to_csv(t64, index=False)
    written.append(t64)

    if profiles_path is None:
        from quaketwin.config import ProjectSettings

        profiles_path = ProjectSettings().project_root / "data/processed/dhaka_building_profiles.gpkg"

    gdf = gpd.read_file(profiles_path, columns=["lon", "lat", "collapse_probability", "population_est"])
    gdf["grid_lon"] = (gdf["lon"] / 0.0045).round() * 0.0045
    gdf["grid_lat"] = (gdf["lat"] / 0.0045).round() * 0.0045
    grid = (
        gdf.groupby(["grid_lon", "grid_lat"])
        .agg(
            building_count=("collapse_probability", "count"),
            mean_collapse_p=("collapse_probability", "mean"),
            total_population=("population_est", "sum"),
        )
        .reset_index()
        .sort_values("mean_collapse_p", ascending=False)
        .head(30)
        .round(4)
    )
    t65 = out_dir / "T6_5_top30_high_risk_grid_cells.csv"
    grid.to_csv(t65, index=False)
    written.append(t65)

    t66 = out_dir / "T6_6_building_features.csv"
    pd.DataFrame(
        [
            {"feature": "construction_type", "source": "OSM building=* tag", "method": "Normalized taxonomy"},
            {"feature": "height_m", "source": "OSM levels/height", "method": "3 m/floor default by class"},
            {"feature": "amplified_pga_g", "source": "Phase 1 hazard grid", "method": "Nearest-cell join"},
            {"feature": "liquefaction_index", "source": "Phase 1 hazard grid", "method": "Nearest-cell join"},
            {"feature": "population_est", "source": "WorldPop 2020", "method": "Density x footprint area"},
            {"feature": "collapse_probability", "source": "Fragility model", "method": "Logistic HAZUS-style"},
        ]
    ).to_csv(t66, index=False)
    written.append(t66)

    return written
