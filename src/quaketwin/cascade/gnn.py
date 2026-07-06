"""Physics-informed graph surrogate emulator for Monte Carlo cascade simulation.

Production architecture: GraphSAGE (selected after ablation; see gnn_models.py).
GCN and other variants are retained for architecture comparison only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd

from quaketwin.config import ProjectSettings
from quaketwin.cascade.graph import build_infrastructure_graph
from quaketwin.cascade.gnn_models import ArchName, SurrogateModel

DEFAULT_ARCH: ArchName = "graphsage"

_NODE_TYPES = ("power", "comm_tower", "bridge", "hospital")


def _node_features(g: nx.DiGraph, nodes: list[str], direct_p: pd.Series) -> np.ndarray:
    rows = []
    for n in nodes:
        d = g.nodes[n]
        one_hot = [1.0 if d["node_type"] == t else 0.0 for t in _NODE_TYPES]
        rows.append(
            one_hot
            + [
                d["amplified_pga_g"],
                d["liquefaction_index"],
                float(g.in_degree(n)),
                float(g.out_degree(n)),
                float(direct_p[n]),
            ]
        )
    x = np.array(rows, dtype=np.float32)
    cont = x[:, len(_NODE_TYPES) :]
    mean, std = cont.mean(axis=0), cont.std(axis=0) + 1e-8
    x[:, len(_NODE_TYPES) :] = (cont - mean) / std
    return x


def _normalized_adjacency(g: nx.DiGraph, nodes: list[str]):
    """Symmetric-normalized (A + I) over the undirected infra subgraph."""
    import torch

    index = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    rows, cols = list(range(n)), list(range(n))
    for u, v in g.edges():
        if u in index and v in index:
            rows.extend([index[u], index[v]])
            cols.extend([index[v], index[u]])
    vals = np.ones(len(rows), dtype=np.float32)
    a = torch.sparse_coo_tensor(
        torch.tensor([rows, cols], dtype=torch.long), torch.tensor(vals), (n, n)
    ).coalesce()
    deg = torch.sparse.sum(a, dim=1).to_dense()
    d_inv_sqrt = deg.pow(-0.5)
    r, c = a.indices()
    norm_vals = a.values() * d_inv_sqrt[r] * d_inv_sqrt[c]
    return torch.sparse_coo_tensor(a.indices(), norm_vals, (n, n)).coalesce()


def train_cascade_gnn(
    period: str = "midday",
    hidden: int = 32,
    epochs: int = 400,
    lr: float = 0.01,
    seed: int = 42,
    arch: ArchName = DEFAULT_ARCH,
) -> dict[str, Any]:
    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    root = ProjectSettings().project_root

    nodes_path = root / "data/processed/cascade_nodes_phase5.gpkg"
    import geopandas as gpd

    mc = gpd.read_file(nodes_path, ignore_geometry=True)
    mc = pd.DataFrame(mc).set_index("node_id")

    print(f"Rebuilding dependency graph for surrogate emulator ({arch})...", flush=True)
    g = build_infrastructure_graph(period=period)
    infra_nodes = [n for n, d in g.nodes(data=True) if d["node_type"] != "zone" and n in mc.index]

    x_np = _node_features(g, infra_nodes, mc["direct_failure_p"])
    y_np = mc.loc[infra_nodes, "total_failure_p"].to_numpy(dtype=np.float32)
    direct_np = mc.loc[infra_nodes, "direct_failure_p"].to_numpy(dtype=np.float32)

    a_hat = _normalized_adjacency(g, infra_nodes)
    x = torch.tensor(x_np)
    y = torch.tensor(y_np)

    n = len(infra_nodes)
    perm = rng.permutation(n)
    n_test = int(0.25 * n)
    test_idx = torch.tensor(perm[:n_test], dtype=torch.long)
    train_idx = torch.tensor(perm[n_test:], dtype=torch.long)

    print(
        f"Training {arch}: {n} nodes ({len(train_idx)} train / {len(test_idx)} test), "
        f"{x.shape[1]} features, {epochs} epochs",
        flush=True,
    )

    model = SurrogateModel(arch, x.shape[1], hidden)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = torch.nn.MSELoss()
    model.train()
    for epoch in range(epochs):
        opt.zero_grad()
        pred = model(a_hat, x)
        loss = loss_fn(pred[train_idx], y[train_idx])
        loss.backward()
        opt.step()
        if (epoch + 1) % 100 == 0:
            print(f"  epoch {epoch + 1}: train MSE = {loss.item():.5f}", flush=True)

    model.eval()
    with torch.no_grad():
        pred = model(a_hat, x).numpy()

    def _metrics(y_true: np.ndarray, y_hat: np.ndarray) -> dict[str, float]:
        mae = float(np.abs(y_true - y_hat).mean())
        ss_res = float(((y_true - y_hat) ** 2).sum())
        ss_tot = float(((y_true - y_true.mean()) ** 2).sum())
        return {"mae": round(mae, 4), "r2": round(1 - ss_res / max(ss_tot, 1e-12), 4)}

    test_mask = perm[:n_test]
    surrogate_test = _metrics(y_np[test_mask], pred[test_mask])
    baseline_test = _metrics(y_np[test_mask], direct_np[test_mask])

    models_dir = root / "data/models"
    models_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), models_dir / "cascade_gnn.pt")

    metrics = {
        "period": period,
        "architecture": arch,
        "nodes": n,
        "train_nodes": int(n - n_test),
        "test_nodes": int(n_test),
        "features": int(x.shape[1]),
        "hidden": hidden,
        "epochs": epochs,
        "target": "total_failure_p (Monte Carlo, direct + cascade)",
        "gnn_test": surrogate_test,
        "baseline_direct_fragility_test": baseline_test,
        "note": (
            f"Production surrogate: {arch}. Trained on Monte Carlo cascade labels; "
            "baseline uses direct fragility only (no cascade)."
        ),
        "model_path": str(models_dir / "cascade_gnn.pt"),
    }
    (models_dir / "cascade_gnn_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2), flush=True)

    pred_df = pd.DataFrame(
        {
            "node_id": infra_nodes,
            "total_failure_p_mc": y_np,
            "total_failure_p_gnn": np.round(pred, 4),
            "direct_failure_p": direct_np,
            "is_test": np.isin(np.arange(n), test_mask),
        }
    )
    pred_df.to_csv(root / "data/processed/cascade_gnn_predictions.csv", index=False)
    return metrics
