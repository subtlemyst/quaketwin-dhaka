"""Publication matplotlib style — vector PDF + high-resolution PNG."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

PUBLICATION_RC = {
    "font.size": 12,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "legend.fontsize": 10,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}

# IBM Design colorblind-safe palette
COLORS = {
    "blue": "#648FFF",
    "purple": "#785EF0",
    "magenta": "#DC267F",
    "orange": "#FE6100",
    "gold": "#FFB000",
    "teal": "#009E73",
    "red": "#C0392B",
    "gray": "#555555",
}


def apply_publication_style() -> None:
    plt.rcParams.update(PUBLICATION_RC)


def save_publication_figure(fig, path: Path | str, *, also_png: bool = True) -> list[Path]:
    """Save figure as vector PDF; optionally mirror as 300 dpi PNG."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    pdf_path = path if path.suffix.lower() == ".pdf" else path.with_suffix(".pdf")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    written.append(pdf_path)
    if also_png:
        png_path = pdf_path.with_suffix(".png")
        fig.savefig(png_path, bbox_inches="tight", facecolor="white", dpi=300)
        written.append(png_path)
    return written
