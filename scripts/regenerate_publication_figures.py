#!/usr/bin/env python3
"""Regenerate all publication figures (PDF + 300 dpi PNG) and sync to paper/figures/."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PAPER_FIG = ROOT / "paper" / "figures"
PHASE_DIRS = [
    ROOT / "outputs" / "phase2" / "figures",
    ROOT / "outputs" / "phase3" / "figures",
    ROOT / "outputs" / "phase4" / "figures",
    ROOT / "outputs" / "phase5" / "figures",
]


def _copy_to_paper() -> list[str]:
    PAPER_FIG.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for phase_dir in PHASE_DIRS:
        if not phase_dir.exists():
            continue
        for src in sorted(phase_dir.glob("*.png")):
            dst = PAPER_FIG / src.name
            shutil.copy2(src, dst)
            copied.append(src.name)
        for src in sorted(phase_dir.glob("*.pdf")):
            dst = PAPER_FIG / src.name
            shutil.copy2(src, dst)
    for extra in (ROOT / "outputs" / "mc_convergence.png", ROOT / "outputs" / "mc_convergence.pdf"):
        if extra.exists():
            shutil.copy2(extra, PAPER_FIG / extra.name)
            copied.append(extra.name)
    return copied


def main() -> None:
    from quaketwin.config import ProjectSettings
    from quaketwin.cascade.publish import publish_phase5
    from quaketwin.exposure.publish import publish_phase3
    from quaketwin.publish.figures import generate_all_figures
    from quaketwin.response.publish import publish_phase4

    root = ProjectSettings().project_root
    profiles = root / "data/processed/dhaka_building_profiles.gpkg"

    print("Phase 2 (hazard + vulnerability maps)...", flush=True)
    generate_all_figures(root / "outputs" / "phase2" / "figures", profiles)

    print("Phase 3 (diurnal exposure)...", flush=True)
    publish_phase3()

    print("Phase 4 (response)...", flush=True)
    publish_phase4()

    print("Phase 5 (cascade + surrogate)...", flush=True)
    publish_phase5()

    print("MC convergence figure...", flush=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "mc_convergence_study.py")], check=False)

    print("Digital-twin architecture figure...", flush=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_dt_architecture_figure.py")], check=True)

    copied = _copy_to_paper()
    print(f"Synced {len(copied)} files to {PAPER_FIG}", flush=True)


if __name__ == "__main__":
    main()
