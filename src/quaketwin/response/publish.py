"""Phase 4 publication outputs."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

from quaketwin.config import ProjectSettings
from quaketwin.publish.style import apply_publication_style, save_publication_figure, COLORS


def publish_phase4(out_dir: Path | None = None) -> dict:
    root = ProjectSettings().project_root.resolve()
    out_dir = (out_dir or root / "outputs" / "phase4").resolve()
    fig_dir = out_dir / "figures"
    tab_dir = out_dir / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tab_dir.mkdir(parents=True, exist_ok=True)
    apply_publication_style()

    summary_path = root / "data/processed/response_phase4_summary.json"
    buildings_path = root / "data/processed/dhaka_response_phase4.gpkg"
    hospitals_path = root / "data/processed/dhaka_hospital_load_phase4.gpkg"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    buildings = gpd.read_file(buildings_path)
    hospitals = gpd.read_file(hospitals_path)

    hospitals_df = pd.DataFrame(hospitals.drop(columns="geometry", errors="ignore"))
    hospitals_df.sort_values("overload_ratio", ascending=False).to_csv(
        tab_dir / "T8_1_hospital_overload.csv", index=False
    )

    top_buildings = (
        buildings.sort_values("rescue_priority_score", ascending=False)
        .head(100)[
            [
                "building_id",
                "collapse_probability",
                "response_time_min",
                "rescue_priority_score",
                "hospital_name",
            ]
        ]
    )
    top_buildings.to_csv(tab_dir / "T8_2_top_rescue_priority_buildings.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 5))
    top_h = hospitals_df.sort_values("overload_ratio", ascending=False).head(15).copy()
    label_col = "name" if "name" in top_h.columns else "hospital_name"
    top_h["label"] = top_h.get(label_col, pd.Series(["Unnamed"] * len(top_h))).fillna("Unnamed")
    ax.barh(top_h["label"], top_h["overload_ratio"], color=COLORS["red"])
    ax.set_xlabel("Overload ratio")
    ax.set_title("F8.1 — Hospital overload ratio (top 15)")
    fig.tight_layout()
    save_publication_figure(fig, fig_dir / "F8_1_hospital_overload.png")
    plt.close(fig)

    sample = buildings.sample(n=min(80000, len(buildings)), random_state=42)
    fig, ax = plt.subplots(figsize=(8, 7))
    sc = ax.scatter(
        sample["lon"],
        sample["lat"],
        c=sample["rescue_priority_score"],
        cmap="plasma",
        s=0.4,
        alpha=0.7,
        vmin=0,
        vmax=1,
    )
    plt.colorbar(sc, ax=ax, label="Rescue priority")
    ax.set_title("F8.2 — Rescue priority across Dhaka")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    fig.tight_layout()
    save_publication_figure(fig, fig_dir / "F8_2_rescue_priority_map.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(buildings["response_time_min"], bins=40, color=COLORS["blue"], alpha=0.8)
    ax.set_xlabel("Response time (minutes)")
    ax.set_ylabel("Building count")
    ax.set_title("F8.3 — Response time distribution")
    fig.tight_layout()
    save_publication_figure(fig, fig_dir / "F8_3_response_time_histogram.png")
    plt.close(fig)

    manifest = {
        "phase": 4,
        "summary": summary,
        "tables": [
            str((tab_dir / "T8_1_hospital_overload.csv").relative_to(root)),
            str((tab_dir / "T8_2_top_rescue_priority_buildings.csv").relative_to(root)),
        ],
        "figures": [
            str((fig_dir / "F8_1_hospital_overload.png").relative_to(root)),
            str((fig_dir / "F8_2_rescue_priority_map.png").relative_to(root)),
            str((fig_dir / "F8_3_response_time_histogram.png").relative_to(root)),
        ],
    }
    (out_dir / "publish_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
