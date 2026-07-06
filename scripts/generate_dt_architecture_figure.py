#!/usr/bin/env python3
"""Digital-twin architecture diagram for manuscript."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from quaketwin.config import ProjectSettings
from quaketwin.publish.style import apply_publication_style, save_publication_figure

# Colorblind-safe palette (IBM Design)
_COLORS = {
    "sensor": "#648FFF",
    "hazard": "#785EF0",
    "building": "#DC267F",
    "cascade": "#FE6100",
    "gnn": "#FFB000",
    "dash": "#000000",
    "feed": "#009E73",
}


def _box(ax, xy, text, color, width=2.6, height=0.55):
    x, y = xy
    patch = FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        boxstyle="round,pad=0.03,rounding_size=0.08",
        linewidth=1.5,
        edgecolor=color,
        facecolor=color,
        alpha=0.18,
    )
    ax.add_patch(patch)
    ax.text(x, y, text, ha="center", va="center", fontsize=12, fontweight="bold")


def _arrow(ax, start, end):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.8,
            color="#333333",
        )
    )


def generate_dt_architecture_figure(out_dir: Path | None = None) -> list[Path]:
    apply_publication_style()
    root = ProjectSettings().project_root
    out_dir = out_dir or root / "paper/figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.5, 9))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis("off")

    # Live feeds (left)
    feeds = [
        (1.6, 10.2, "Seismic\nsensors"),
        (1.6, 8.8, "Hospital\nstatus"),
        (1.6, 7.4, "Utility SCADA\n(power, comms)"),
        (1.6, 6.0, "OSM / WorldPop\nupdates"),
    ]
    for x, y, label in feeds:
        _box(ax, (x, y), label, _COLORS["feed"], width=2.2, height=0.7)
        _arrow(ax, (x + 1.15, y), (3.35, y))

    # Pipeline stack (center)
    stack = [
        (5.0, 10.2, "Hazard engine\n(GMPE logic-tree, Vs30)", _COLORS["hazard"]),
        (5.0, 8.6, "Building graph\n(fragility, exposure)", _COLORS["building"]),
        (5.0, 7.0, "Cascade simulation\n(Monte Carlo lifelines)", _COLORS["cascade"]),
        (5.0, 5.4, "Physics-informed\nsurrogate emulator", _COLORS["gnn"]),
        (5.0, 3.6, "Dashboard / API\n(Phase 6 digital twin)", _COLORS["dash"]),
    ]
    for x, y, label, color in stack:
        _box(ax, (x, y), label, color)
    for i in range(len(stack) - 1):
        _arrow(ax, (5.0, stack[i][1] - 0.35), (5.0, stack[i + 1][1] + 0.35))

    # Calibration loop
    ax.annotate(
        "Physics pipeline\ncalibration runs",
        xy=(5.0, 5.4),
        xytext=(8.2, 5.4),
        fontsize=11,
        ha="center",
        arrowprops=dict(arrowstyle="<->", color="#555555", lw=1.4),
    )

    ax.text(
        5.0,
        11.3,
        "QuakeTwin digital-twin architecture",
        ha="center",
        fontsize=15,
        fontweight="bold",
    )
    ax.text(
        5.0,
        1.6,
        "State: building + infrastructure graphs  |  Simulation: hazard–fragility–cascade  |  Surrogate: physics-informed emulator",
        ha="center",
        fontsize=10,
        color="#444444",
    )

    written: list[Path] = []
    save_publication_figure(fig, out_dir / "dt_architecture.png")
    written.extend([out_dir / "dt_architecture.pdf", out_dir / "dt_architecture.png"])
    plt.close(fig)
    return written


def main() -> None:
    paths = generate_dt_architecture_figure()
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
