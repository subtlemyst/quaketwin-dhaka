"""Monte Carlo cascade simulation over the lifeline dependency graph (Phase 5).

Each iteration:

1. Direct seismic failures are sampled per infrastructure node from a logistic
   fragility on soil-amplified PGA plus a liquefaction boost.
2. Failures propagate: overloaded interconnected substations, towers that lose
   all feeding substations, hospitals that lose grid power (backup generators
   folded into the conditional probability).
3. Zones lose services when all their providers are down; service loss maps to
   a rescue-delay multiplier that couples back to the Phase 4 response model.

Aggregating over iterations yields per-node failure probabilities and per-zone
expected rescue-delay factors.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd

from quaketwin.config import ProjectSettings
from quaketwin.cascade.graph import build_infrastructure_graph, graph_summary, load_cascade_config

_INFRA_TYPES = ("power", "comm_tower", "bridge", "hospital")


def _direct_failure_probability(g: nx.DiGraph, cfg: dict[str, Any]) -> dict[str, float]:
    frag = cfg["seismic_fragility"]
    k = float(frag["logistic_k"])
    liq_max = float(frag["liquefaction_boost_max"])
    medians = frag["median_capacity_g"]
    probs: dict[str, float] = {}
    for nid, d in g.nodes(data=True):
        if d["node_type"] == "zone":
            continue
        median_key = d.get("infra_kind", d["node_type"])
        median = float(medians.get(median_key, medians.get(d["node_type"], 0.45)))
        base = 1.0 / (1.0 + np.exp(-k * (d["amplified_pga_g"] - median)))
        p = min(1.0, base + liq_max * d["liquefaction_index"])
        probs[nid] = float(p)
    return probs


def _providers(g: nx.DiGraph, nid: str, service: str) -> list[str]:
    return [u for u, _, d in g.in_edges(nid, data=True) if d["service"] == service]


def run_cascade(
    period: str = "midday",
    output_dir: Path | None = None,
    hazard_path: Path | None = None,
    scenario_id: str = "dhaka_mw72_dauki",
    n_iterations: int | None = None,
    propagation_overrides: dict[str, float] | None = None,
    write_outputs: bool = True,
) -> dict[str, Any]:
    cfg = load_cascade_config()
    mc = cfg["monte_carlo"]
    prop = dict(cfg["propagation"])
    if propagation_overrides:
        prop.update(propagation_overrides)
    delay = cfg["rescue_delay"]
    rng = np.random.default_rng(int(mc["seed"]))
    n_iter = int(n_iterations or mc["iterations"])

    root = ProjectSettings().project_root
    output_dir = output_dir or root / "data/processed"

    if write_outputs:
        print(f"Building infrastructure graph ({scenario_id})...", flush=True)
    g = build_infrastructure_graph(period=period, hazard_path=hazard_path)
    gsum = graph_summary(g)
    if write_outputs:
        print(json.dumps(gsum, indent=2), flush=True)

    direct_p = _direct_failure_probability(g, cfg)
    infra_nodes = [n for n, d in g.nodes(data=True) if d["node_type"] != "zone"]
    zone_nodes = [n for n, d in g.nodes(data=True) if d["node_type"] == "zone"]

    # Pre-resolve dependency lists once (graph is static across iterations)
    power_nodes = [n for n in infra_nodes if g.nodes[n]["node_type"] == "power"]
    tower_nodes = [n for n in infra_nodes if g.nodes[n]["node_type"] == "comm_tower"]
    hospital_nodes = [n for n in infra_nodes if g.nodes[n]["node_type"] == "hospital"]

    grid_neighbors = {n: _providers(g, n, "grid") for n in power_nodes}
    tower_power = {n: _providers(g, n, "power") for n in tower_nodes}
    hospital_power = {n: _providers(g, n, "power") for n in hospital_nodes}
    zone_power = {z: _providers(g, z, "power") for z in zone_nodes}
    zone_comm = {z: _providers(g, z, "comm") for z in zone_nodes}
    zone_access = {z: _providers(g, z, "access") for z in zone_nodes}

    fail_count = {n: 0 for n in infra_nodes}
    cascade_only_count = {n: 0 for n in infra_nodes}
    zone_power_lost = {z: 0 for z in zone_nodes}
    zone_comm_lost = {z: 0 for z in zone_nodes}
    zone_bridge_out = {z: 0 for z in zone_nodes}
    zone_delay_sum = {z: 0.0 for z in zone_nodes}
    iter_pop_delay: list[float] = []

    p_sub_sub = float(prop["substation_to_substation"])
    p_sub_tower = float(prop["substation_to_tower"])
    p_sub_hosp = float(prop["substation_to_hospital"])
    max_iter = int(prop["max_iterations"])

    if write_outputs:
        print(f"Running {n_iter} Monte Carlo iterations...", flush=True)
    for it in range(n_iter):
        failed = {n: rng.random() < direct_p[n] for n in infra_nodes}
        direct = dict(failed)

        # Cascade within power grid, then to towers/hospitals
        for _ in range(max_iter):
            changed = False
            for n in power_nodes:
                if failed[n]:
                    continue
                down = sum(1 for m in grid_neighbors[n] if failed[m])
                if down and rng.random() < 1 - (1 - p_sub_sub) ** down:
                    failed[n] = True
                    changed = True
            for n in tower_nodes:
                if failed[n]:
                    continue
                prov = tower_power[n]
                if prov and all(failed[m] for m in prov) and rng.random() < p_sub_tower:
                    failed[n] = True
                    changed = True
            for n in hospital_nodes:
                if failed[n]:
                    continue
                prov = hospital_power[n]
                if prov and all(failed[m] for m in prov) and rng.random() < p_sub_hosp:
                    failed[n] = True
                    changed = True
            if not changed:
                break

        for n in infra_nodes:
            if failed[n]:
                fail_count[n] += 1
                if not direct[n]:
                    cascade_only_count[n] += 1

        pop_weights = np.array([g.nodes[z]["population"] for z in zone_nodes], dtype=float)
        pop_sum = max(float(pop_weights.sum()), 1.0)
        iter_weighted_delay = 0.0
        for z in zone_nodes:
            p_lost = bool(zone_power[z]) and all(failed[m] for m in zone_power[z])
            c_lost = bool(zone_comm[z]) and all(failed[m] for m in zone_comm[z])
            b_out = any(failed[m] for m in zone_access[z])
            if p_lost:
                zone_power_lost[z] += 1
            if c_lost:
                zone_comm_lost[z] += 1
            if b_out:
                zone_bridge_out[z] += 1
            factor = (
                1.0
                + delay["comm_loss_factor"] * c_lost
                + delay["power_loss_factor"] * p_lost
                + delay["bridge_out_factor"] * b_out
            )
            zone_delay_sum[z] += factor
            iter_weighted_delay += g.nodes[z]["population"] * factor
        iter_pop_delay.append(iter_weighted_delay / pop_sum)

        if write_outputs and (it + 1) % 100 == 0:
            print(f"  ... iteration {it + 1}/{n_iter}", flush=True)

    # --- assemble outputs ---
    node_rows = []
    for n in infra_nodes:
        d = g.nodes[n]
        node_rows.append(
            {
                "node_id": n,
                "node_type": d["node_type"],
                "name": d.get("name", ""),
                "lon": d["lon"],
                "lat": d["lat"],
                "amplified_pga_g": d["amplified_pga_g"],
                "liquefaction_index": d["liquefaction_index"],
                "direct_failure_p": round(direct_p[n], 4),
                "total_failure_p": round(fail_count[n] / n_iter, 4),
                "cascade_failure_p": round(cascade_only_count[n] / n_iter, 4),
            }
        )
    nodes_df = pd.DataFrame(node_rows)
    nodes_gdf = gpd.GeoDataFrame(
        nodes_df,
        geometry=gpd.points_from_xy(nodes_df["lon"], nodes_df["lat"]),
        crs="EPSG:4326",
    )

    zone_rows = []
    for z in zone_nodes:
        d = g.nodes[z]
        zone_rows.append(
            {
                "zone_id": z,
                "lon": d["lon"],
                "lat": d["lat"],
                "population": d["population"],
                "casualties": d["casualties"],
                "mean_collapse_p": d["mean_collapse_p"],
                "buildings": d["buildings"],
                "p_power_lost": round(zone_power_lost[z] / n_iter, 4),
                "p_comm_lost": round(zone_comm_lost[z] / n_iter, 4),
                "p_bridge_out": round(zone_bridge_out[z] / n_iter, 4),
                "expected_delay_factor": round(zone_delay_sum[z] / n_iter, 4),
            }
        )
    zones_df = pd.DataFrame(zone_rows)
    zones_gdf = gpd.GeoDataFrame(
        zones_df,
        geometry=gpd.points_from_xy(zones_df["lon"], zones_df["lat"]),
        crs="EPSG:4326",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = output_dir / f"cascade_nodes_{scenario_id}.gpkg"
    zones_path = output_dir / f"cascade_zones_{scenario_id}.gpkg"
    if write_outputs:
        nodes_gdf.to_file(nodes_path, driver="GPKG", layer="cascade_nodes")
        zones_gdf.to_file(zones_path, driver="GPKG", layer="cascade_zones")

    by_type = (
        nodes_df.groupby("node_type")[["direct_failure_p", "total_failure_p", "cascade_failure_p"]]
        .mean()
        .round(4)
        .to_dict("index")
    )
    pop = zones_df["population"].to_numpy(dtype=float)
    delay_mean = float((zones_df["expected_delay_factor"] * pop).sum() / pop.sum())
    delay_std = float(np.std(iter_pop_delay, ddof=1)) if len(iter_pop_delay) > 1 else 0.0
    delay_ci95 = (
        round(delay_mean - 1.96 * delay_std / math.sqrt(n_iter), 4),
        round(delay_mean + 1.96 * delay_std / math.sqrt(n_iter), 4),
    )
    summary = {
        "scenario_id": scenario_id,
        "period": period,
        "monte_carlo_iterations": n_iter,
        "propagation_baseline": dict(cfg["propagation"]),
        "propagation_used": prop,
        "graph": gsum,
        "mean_failure_by_type": by_type,
        "cascade_amplification": {
            t: round(
                float(
                    nodes_df.loc[nodes_df["node_type"] == t, "total_failure_p"].mean()
                    / max(nodes_df.loc[nodes_df["node_type"] == t, "direct_failure_p"].mean(), 1e-9)
                ),
                3,
            )
            for t in nodes_df["node_type"].unique()
        },
        "population_weighted": {
            "p_power_lost": round(float((zones_df["p_power_lost"] * pop).sum() / pop.sum()), 4),
            "p_comm_lost": round(float((zones_df["p_comm_lost"] * pop).sum() / pop.sum()), 4),
            "p_bridge_out": round(float((zones_df["p_bridge_out"] * pop).sum() / pop.sum()), 4),
            "expected_delay_factor": round(delay_mean, 4),
            "expected_delay_factor_std": round(delay_std, 4),
            "expected_delay_factor_ci95": list(delay_ci95),
        },
        "worst_zones": zones_df.nlargest(10, "expected_delay_factor")[
            ["zone_id", "population", "casualties", "p_power_lost", "p_comm_lost", "p_bridge_out", "expected_delay_factor"]
        ].to_dict("records"),
        "outputs": {"nodes": str(nodes_path), "zones": str(zones_path)} if write_outputs else {},
    }

    if write_outputs:
        summary_path = output_dir / f"cascade_{scenario_id}_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in summary.items() if k != "worst_zones"}, indent=2), flush=True)
        print(f"Written: {nodes_path}", flush=True)
        print(f"Written: {zones_path}", flush=True)
    return summary


def run_cascade_with_overrides(
    period: str = "midday",
    n_iterations: int = 150,
    propagation_overrides: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Fast cascade run for sensitivity analysis (no file writes)."""
    return run_cascade(
        period=period,
        n_iterations=n_iterations,
        propagation_overrides=propagation_overrides,
        write_outputs=False,
    )
