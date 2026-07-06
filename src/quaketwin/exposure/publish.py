"""Phase 3 publication figures and tables."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from quaketwin.config import ProjectSettings
from quaketwin.publish.style import apply_publication_style, save_publication_figure, COLORS


def publish_phase3(out_dir: Path | None = None) -> dict:
    root = ProjectSettings().project_root.resolve()
    out_dir = (out_dir or root / "outputs" / "phase3").resolve()
    summary_path = root / "data/processed/diurnal_exposure_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    df = pd.DataFrame(summary["periods"])

    fig_dir = out_dir / "figures"
    tab_dir = out_dir / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tab_dir.mkdir(parents=True, exist_ok=True)
    apply_publication_style()

    df.to_csv(tab_dir / "T7_1_diurnal_exposure_summary.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    axes[0].bar(df["label"], df["high_risk_population"] / 1e6, color=COLORS["blue"])
    axes[0].set_ylabel("Population in high-risk buildings (millions)")
    axes[0].set_title("F7.1 — High-risk exposure by time of day")
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].bar(df["label"], df["expected_casualties"] / 1000, color=COLORS["red"])
    axes[1].set_ylabel("Expected casualties (thousands)")
    axes[1].set_title("F7.2 — Expected casualties by time of day")
    axes[1].tick_params(axis="x", rotation=20)

    fig.tight_layout()
    save_publication_figure(fig, fig_dir / "F7_1_diurnal_population_casualties.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(df["hour"], df["high_risk_population"] / 1e6, "o-", linewidth=2, label="High-risk population")
    ax2 = ax.twinx()
    ax2.plot(df["hour"], df["expected_casualties"] / 1000, "s--", color=COLORS["red"], label="Casualties")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Population in high-risk buildings (millions)")
    ax2.set_ylabel("Casualties (thousands)")
    ax.set_title("F7.3 — Diurnal exposure curve (Mw 7.2 Dauki)")
    ax.set_xticks(df["hour"])
    save_publication_figure(fig, fig_dir / "F7_3_diurnal_exposure_curve.png")
    plt.close(fig)

    manifest = {
        "phase": 3,
        "summary": summary,
        "tables": [str((tab_dir / "T7_1_diurnal_exposure_summary.csv").relative_to(root))],
        "figures": [
            str((fig_dir / "F7_1_diurnal_population_casualties.png").relative_to(root)),
            str((fig_dir / "F7_3_diurnal_exposure_curve.png").relative_to(root)),
        ],
    }
    (out_dir / "publish_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
