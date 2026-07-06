"""Monte Carlo convergence study for cascade delay factor (Mw 7.2 Dauki).

Runs the cascade simulator at increasing iteration counts and writes
outputs/mc_convergence.json plus outputs/mc_convergence.png for the paper.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    from quaketwin.cascade.simulate import run_cascade
    from quaketwin.publish.style import apply_publication_style, save_publication_figure

    apply_publication_style()

    counts = [50, 100, 200, 300, 500]
    delays: list[float] = []
    print("MC convergence study (Mw 7.2 Dauki, midday)", flush=True)
    for n in counts:
        summary = run_cascade(period="midday", n_iterations=n)
        d = float(summary["population_weighted"]["expected_delay_factor"])
        delays.append(d)
        print(f"  N={n:4d}  delay_factor={d:.4f}", flush=True)

    out_dir = ROOT / "outputs"
    out_dir.mkdir(exist_ok=True)
    payload = {"iterations": counts, "expected_delay_factor": delays}
    (out_dir / "mc_convergence.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(counts, delays, "o-", linewidth=2, markersize=6)
    ax.axhline(delays[-1], color="gray", linestyle="--", linewidth=1, label=f"N=500 ref ({delays[-1]:.3f})")
    ax.set_xlabel("Monte Carlo iterations")
    ax.set_ylabel("Population-weighted delay factor")
    ax.set_title("Cascade MC convergence (Mw 7.2 Dauki)")
    ax.legend()
    fig.tight_layout()
    save_publication_figure(fig, out_dir / "mc_convergence.png")
    plt.close(fig)
    print(f"Wrote {out_dir / 'mc_convergence.json'}", flush=True)


if __name__ == "__main__":
    main()
