"""GNN architecture ablation: GCN vs GraphSAGE vs GAT vs GIN vs MLP."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    import numpy as np
    import pandas as pd
    import torch

    from quaketwin.cascade.gnn import _node_features, _normalized_adjacency
    from quaketwin.cascade.gnn_models import ArchName, train_architecture
    from quaketwin.cascade.graph import build_infrastructure_graph
    from quaketwin.config import ProjectSettings

    root = ProjectSettings().project_root
    import geopandas as gpd

    mc = gpd.read_file(root / "data/processed/cascade_nodes_phase5.gpkg", ignore_geometry=True)
    mc = pd.DataFrame(mc).set_index("node_id")
    g = build_infrastructure_graph(period="midday")
    infra_nodes = [n for n, d in g.nodes(data=True) if d["node_type"] != "zone" and n in mc.index]

    x_np = _node_features(g, infra_nodes, mc["direct_failure_p"])
    y_np = mc.loc[infra_nodes, "total_failure_p"].to_numpy(dtype=np.float32)
    direct_np = mc.loc[infra_nodes, "direct_failure_p"].to_numpy(dtype=np.float32)

    a_hat = _normalized_adjacency(g, infra_nodes)
    x = torch.tensor(x_np)
    y = torch.tensor(y_np)

    rng = np.random.default_rng(42)
    n = len(infra_nodes)
    perm = rng.permutation(n)
    n_test = int(0.25 * n)
    test_idx = torch.tensor(perm[:n_test], dtype=torch.long)
    train_idx = torch.tensor(perm[n_test:], dtype=torch.long)

    archs: list[ArchName] = ["gcn", "graphsage", "gat", "gin", "mlp"]
    rows = []
    print("GNN architecture ablation (75/25 node split, Mw 7.2 Dauki)", flush=True)
    for arch in archs:
        print(f"  training {arch}...", flush=True)
        metrics = train_architecture(
            arch, a_hat, x, y, train_idx, test_idx, hidden=32, epochs=300, lr=0.01
        )
        rows.append({"architecture": arch, **metrics})
        print(f"    MAE={metrics['mae']} R2={metrics['r2']}", flush=True)

    baseline_mae = float(np.abs(y_np[perm[:n_test]] - direct_np[perm[:n_test]]).mean())
    ss_res = float(((y_np[perm[:n_test]] - direct_np[perm[:n_test]]) ** 2).sum())
    ss_tot = float(((y_np[perm[:n_test]] - y_np[perm[:n_test]].mean()) ** 2).sum())
    rows.append(
        {
            "architecture": "direct_fragility",
            "mae": round(baseline_mae, 4),
            "r2": round(1 - ss_res / max(ss_tot, 1e-12), 4),
        }
    )

    out = {"split": "75/25 node hold-out", "nodes": n, "results": rows}
    out_path = root / "outputs/gnn_architecture_ablation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    csv_path = root / "outputs/phase5/tables/T9_4_gnn_architecture_ablation.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    print(json.dumps(out, indent=2), flush=True)


if __name__ == "__main__":
    main()
