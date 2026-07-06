"""Phase 5 publication figures and tables (infrastructure cascade)."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

from quaketwin.config import ProjectSettings
from quaketwin.publish.style import apply_publication_style, save_publication_figure, COLORS


def publish_phase5(out_dir: Path | None = None) -> dict:
    root = ProjectSettings().project_root.resolve()
    out_dir = (out_dir or root / "outputs" / "phase5").resolve()
    fig_dir = out_dir / "figures"
    tab_dir = out_dir / "tables"
    fig_dir.mkdir(parents=True, exist_ok=True)
    tab_dir.mkdir(parents=True, exist_ok=True)
    apply_publication_style()

    summary = json.loads(
        (root / "data/processed/cascade_phase5_summary.json").read_text(encoding="utf-8")
    )
    nodes = pd.DataFrame(
        gpd.read_file(root / "data/processed/cascade_nodes_phase5.gpkg", ignore_geometry=True)
    )
    zones = pd.DataFrame(
        gpd.read_file(root / "data/processed/cascade_zones_phase5.gpkg", ignore_geometry=True)
    )

    # T9.1 — failure probabilities by node type
    by_type = (
        nodes.groupby("node_type")
        .agg(
            count=("node_id", "size"),
            mean_direct_p=("direct_failure_p", "mean"),
            mean_total_p=("total_failure_p", "mean"),
            mean_cascade_p=("cascade_failure_p", "mean"),
        )
        .round(4)
        .reset_index()
    )
    by_type["cascade_amplification"] = (
        by_type["mean_total_p"] / by_type["mean_direct_p"].clip(lower=1e-9)
    ).round(3)
    by_type.to_csv(tab_dir / "T9_1_failure_by_node_type.csv", index=False)

    # T9.2 — worst zones by expected rescue delay
    worst = zones.nlargest(20, "expected_delay_factor")[
        [
            "zone_id", "population", "casualties", "p_power_lost",
            "p_comm_lost", "p_bridge_out", "expected_delay_factor",
        ]
    ]
    worst.to_csv(tab_dir / "T9_2_worst_zones_rescue_delay.csv", index=False)

    # F9.1 — direct vs total failure by node type
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(by_type))
    w = 0.38
    ax.bar([i - w / 2 for i in x], by_type["mean_direct_p"], w, label="Direct (seismic only)", color=COLORS["blue"])
    ax.bar([i + w / 2 for i in x], by_type["mean_total_p"], w, label="Total (with cascade)", color=COLORS["red"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(by_type["node_type"])
    ax.set_ylabel("Mean failure probability")
    ax.set_title("F9.1 — Cascade amplification of failure probability (Mw 7.2 Dauki)")
    ax.legend()
    fig.tight_layout()
    save_publication_figure(fig, fig_dir / "F9_1_cascade_amplification.png")
    plt.close(fig)

    # F9.2 — map of expected rescue delay factor
    fig, ax = plt.subplots(figsize=(9, 8))
    sc = ax.scatter(
        zones["lon"], zones["lat"],
        c=zones["expected_delay_factor"], s=28, cmap="YlOrRd", marker="s",
    )
    pnodes = nodes[nodes["node_type"] == "power"]
    ax.scatter(pnodes["lon"], pnodes["lat"], s=30, c="black", marker="^", label="Power nodes")
    fig.colorbar(sc, ax=ax, label="Expected rescue-delay factor")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("F9.2 — Expected rescue-delay factor from lifeline failures")
    ax.legend(loc="upper right")
    fig.tight_layout()
    save_publication_figure(fig, fig_dir / "F9_2_rescue_delay_map.png")
    plt.close(fig)

    # F9.3 — service loss probability vs population (exposure concentration)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(zones["p_power_lost"], zones["population"] / 1000, s=14, alpha=0.5, label="Power", color="#2980b9")
    ax.scatter(zones["p_comm_lost"], zones["population"] / 1000, s=14, alpha=0.5, label="Communication", color="#8e44ad")
    ax.set_xlabel("Probability service lost")
    ax.set_ylabel("Zone population (thousands)")
    ax.set_title("F9.3 — Population exposed to lifeline service loss")
    ax.legend()
    fig.tight_layout()
    save_publication_figure(fig, fig_dir / "F9_3_service_loss_vs_population.png")
    plt.close(fig)

    figures = [
        "F9_1_cascade_amplification.png",
        "F9_2_rescue_delay_map.png",
        "F9_3_service_loss_vs_population.png",
    ]
    tables = ["T9_1_failure_by_node_type.csv", "T9_2_worst_zones_rescue_delay.csv"]

    # F9.4 / T9.3 — GNN surrogate quality (if trained)
    gnn_pred_path = root / "data/processed/cascade_gnn_predictions.csv"
    gnn_metrics_path = root / "data/models/cascade_gnn_metrics.json"
    gnn_metrics = None
    if gnn_pred_path.exists() and gnn_metrics_path.exists():
        gnn_metrics = json.loads(gnn_metrics_path.read_text(encoding="utf-8"))
        pred = pd.read_csv(gnn_pred_path)
        test = pred[pred["is_test"]]
        arch = gnn_metrics.get("architecture", "graphsage")
        fig, ax = plt.subplots(figsize=(6.5, 6))
        ax.scatter(test["total_failure_p_mc"], test["total_failure_p_gnn"], s=18, alpha=0.6, color=COLORS["teal"])
        lim = [0, max(1.0, test["total_failure_p_mc"].max())]
        ax.plot(lim, lim, "k--", linewidth=1)
        ax.set_xlabel("Monte Carlo total failure probability")
        ax.set_ylabel("Surrogate-predicted failure probability")
        ax.set_title(
            f"F9.4 — Surrogate emulator vs Monte Carlo (test nodes)\n"
            f"{arch.upper()} MAE = {gnn_metrics['gnn_test']['mae']}, "
            f"R² = {gnn_metrics['gnn_test']['r2']}"
        )
        fig.tight_layout()
        save_publication_figure(fig, fig_dir / "F9_4_gnn_vs_montecarlo.png")
        plt.close(fig)
        figures.append("F9_4_gnn_vs_montecarlo.png")

        pd.DataFrame(
            [
                {"model": f"Surrogate ({arch})", **gnn_metrics["gnn_test"]},
                {"model": "Direct fragility baseline", **gnn_metrics["baseline_direct_fragility_test"]},
            ]
        ).to_csv(tab_dir / "T9_3_gnn_surrogate_metrics.csv", index=False)
        tables.append("T9_3_gnn_surrogate_metrics.csv")

    manifest = {
        "phase": 5,
        "summary": summary,
        "gnn_metrics": gnn_metrics,
        "tables": [str((tab_dir / t).relative_to(root)) for t in tables],
        "figures": [str((fig_dir / f).relative_to(root)) for f in figures],
    }
    (out_dir / "publish_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"tables": manifest["tables"], "figures": manifest["figures"]}, indent=2), flush=True)
    return manifest
