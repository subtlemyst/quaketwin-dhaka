"""Cross-scenario physics-informed surrogate emulator (GraphSAGE production)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd

from quaketwin.config import ProjectSettings
from quaketwin.cascade.ensemble import hazard_path_for, load_scenarios_config
from quaketwin.cascade.graph import build_infrastructure_graph
from quaketwin.cascade.gnn import DEFAULT_ARCH, _normalized_adjacency
from quaketwin.cascade.gnn_models import SurrogateModel

_NODE_TYPES = ("power", "comm_tower", "bridge", "hospital")


def _scenario_features(magnitude: float, mean_pga: float, mean_liq: float) -> list[float]:
    return [magnitude / 10.0, mean_pga, mean_liq]


def _load_scenario_samples(
    scenario_id: str,
    magnitude: float,
    period: str,
) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray, nx.DiGraph]:
    root = ProjectSettings().project_root
    nodes_path = root / "data/processed" / f"cascade_nodes_{scenario_id}.gpkg"
    mc = pd.DataFrame(gpd.read_file(nodes_path, ignore_geometry=True)).set_index("node_id")
    g = build_infrastructure_graph(period=period, hazard_path=hazard_path_for(scenario_id))
    infra_nodes = [n for n, d in g.nodes(data=True) if d["node_type"] != "zone" and n in mc.index]

    mean_pga = float(mc["amplified_pga_g"].mean())
    mean_liq = float(mc["liquefaction_index"].mean())
    scen_feat = _scenario_features(magnitude, mean_pga, mean_liq)

    rows = []
    y = []
    direct = []
    for n in infra_nodes:
        d = g.nodes[n]
        one_hot = [1.0 if d["node_type"] == t else 0.0 for t in _NODE_TYPES]
        rows.append(
            one_hot
            + scen_feat
            + [
                d["amplified_pga_g"],
                d["liquefaction_index"],
                float(g.in_degree(n)),
                float(g.out_degree(n)),
                float(mc.loc[n, "direct_failure_p"]),
            ]
        )
        y.append(float(mc.loc[n, "total_failure_p"]))
        direct.append(float(mc.loc[n, "direct_failure_p"]))

    x = np.array(rows, dtype=np.float32)
    return infra_nodes, x, np.array(y, dtype=np.float32), np.array(direct, dtype=np.float32), g


def train_cascade_gnn_ensemble(
    period: str = "midday",
    epochs: int = 500,
    hidden: int = 48,
    arch: str = DEFAULT_ARCH,
) -> dict[str, Any]:
    import torch
    import torch.nn as nn

    cfg = load_scenarios_config()
    root = ProjectSettings().project_root
    torch.manual_seed(42)

    train_specs = cfg["train_scenarios"]
    test_specs = cfg["test_scenarios"]

    train_data = []
    for spec in train_specs:
        nodes, x, y, d, g = _load_scenario_samples(spec["id"], float(spec["magnitude"]), period)
        train_data.append((spec["id"], nodes, x, y, d, g))

    ref_nodes = train_data[0][1]
    for sid, nodes, *_ in train_data:
        if nodes != ref_nodes:
            raise ValueError(f"Node mismatch in {sid}")

    a_hat = _normalized_adjacency(train_data[0][5], ref_nodes)
    in_dim = train_data[0][2].shape[1]

    test_x, test_y, test_d = [], [], []
    for spec in test_specs:
        nodes, x, y, d, _ = _load_scenario_samples(spec["id"], float(spec["magnitude"]), period)
        if nodes != ref_nodes:
            raise ValueError(f"Node mismatch in test scenario {spec['id']}")
        test_x.append(x)
        test_y.append(y)
        test_d.append(d)

    model = SurrogateModel(arch, in_dim, hidden)  # type: ignore[arg-type]
    opt = torch.optim.Adam(model.parameters(), lr=0.008)
    loss_fn = nn.MSELoss()

    print(
        f"Cross-scenario {arch}: {len(train_specs)} train scenarios, "
        f"{len(test_specs)} test scenarios, {len(ref_nodes)} nodes each",
        flush=True,
    )
    model.train()
    for epoch in range(epochs):
        opt.zero_grad()
        total_loss = 0.0
        for _, _, x, y, _, _ in train_data:
            pred = model(a_hat, torch.tensor(x))
            total_loss = total_loss + loss_fn(pred, torch.tensor(y))
        total_loss.backward()
        opt.step()
        if (epoch + 1) % 100 == 0:
            print(f"  epoch {epoch + 1}: train MSE = {(total_loss / len(train_data)).item():.5f}", flush=True)

    model.eval()
    test_preds: list[np.ndarray] = []
    test_trues: list[np.ndarray] = []
    test_dirs: list[np.ndarray] = []
    with torch.no_grad():
        for spec in test_specs:
            _, x, y, d, _ = _load_scenario_samples(spec["id"], float(spec["magnitude"]), period)
            pred = model(a_hat, torch.tensor(x)).numpy()
            test_preds.append(pred)
            test_trues.append(y)
            test_dirs.append(d)
    pred_test = np.concatenate(test_preds)
    y_test_np = np.concatenate(test_trues)
    d_test_np = np.concatenate(test_dirs)

    def _metrics(y_true: np.ndarray, y_hat: np.ndarray) -> dict[str, float]:
        mae = float(np.abs(y_true - y_hat).mean())
        ss_res = float(((y_true - y_hat) ** 2).sum())
        ss_tot = float(((y_true - y_true.mean()) ** 2).sum())
        return {"mae": round(mae, 4), "r2": round(1 - ss_res / max(ss_tot, 1e-12), 4)}

    metrics = {
        "period": period,
        "architecture": arch,
        "training": "cross_scenario",
        "train_scenarios": [s["id"] for s in train_specs],
        "test_scenarios": [s["id"] for s in test_specs],
        "nodes_per_scenario": len(ref_nodes),
        "features": int(in_dim),
        "gnn_test_held_out_scenarios": _metrics(y_test_np, pred_test),
        "baseline_direct_fragility_test": _metrics(y_test_np, d_test_np),
        "note": "Test set comprises all nodes from held-out Madhupur scenarios.",
        "model_path": str(root / "data/models/cascade_gnn_ensemble.pt"),
    }

    models_dir = root / "data/models"
    models_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), models_dir / "cascade_gnn_ensemble.pt")
    (models_dir / "cascade_gnn_ensemble_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2), flush=True)
    return metrics
