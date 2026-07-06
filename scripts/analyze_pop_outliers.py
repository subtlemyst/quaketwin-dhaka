"""Diagnose population outliers in building profiles (consolidation QA)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import geopandas as gpd
import pandas as pd


def main() -> None:
    gdf = gpd.read_file(
        ROOT / "data/processed/dhaka_building_profiles.gpkg",
        columns=[
            "building_id",
            "population_est",
            "footprint_m2",
            "height_m",
            "occupancy_type",
            "construction_type",
            "building",
        ],
    )
    df = pd.DataFrame(gdf.drop(columns="geometry"))

    print("=== population_est distribution ===", flush=True)
    print(df["population_est"].describe([0.5, 0.9, 0.99, 0.999]).round(1), flush=True)
    print(flush=True)

    top = df.nlargest(10, "population_est")[
        ["building_id", "population_est", "footprint_m2", "height_m", "occupancy_type", "building"]
    ]
    print("=== top 10 by population ===", flush=True)
    print(top.to_string(index=False), flush=True)
    print(flush=True)

    row = df[df["building_id"] == 304935722]
    print("=== building 304935722 ===", flush=True)
    print(row.to_string(index=False), flush=True)
    print(flush=True)

    big = df[df["population_est"] > 2000]
    print(f"buildings with pop>2000: {len(big)}, pop in them: {big['population_est'].sum():,}", flush=True)
    print(f"total pop all buildings: {df['population_est'].sum():,}", flush=True)

    # Plausible capacity: floors x footprint / 5 m^2 per person (dense occupancy)
    floors = (df["height_m"] / 3.0).clip(lower=1)
    plausible_cap = (df["footprint_m2"] * floors / 5.0).round()
    over_cap = df[df["population_est"] > plausible_cap]
    print(f"buildings exceeding plausible capacity: {len(over_cap):,}", flush=True)
    print(f"excess population above cap: {(over_cap['population_est'] - plausible_cap[over_cap.index]).sum():,.0f}", flush=True)


if __name__ == "__main__":
    main()
