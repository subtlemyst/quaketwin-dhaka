"""Graph surrogate model zoo for architecture ablation (GCN, GraphSAGE, GAT, GIN, MLP)."""

from __future__ import annotations

from typing import Literal

import torch
import torch.nn as nn
import torch.nn.functional as F

ArchName = Literal["gcn", "graphsage", "gat", "gin", "mlp"]


class GCNLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.lin = nn.Linear(in_dim, out_dim)

    def forward(self, adj: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        return self.lin(torch.sparse.mm(adj, x))


class GraphSAGELayer(nn.Module):
    """Mean-neighbor aggregate (unnormalized adjacency row-mean)."""

    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.lin_self = nn.Linear(in_dim, out_dim)
        self.lin_neigh = nn.Linear(in_dim, out_dim)

    def forward(self, adj: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        neigh = torch.sparse.mm(adj, x)
        deg = torch.sparse.sum(adj, dim=1).to_dense().clamp(min=1.0).unsqueeze(1)
        neigh = neigh / deg
        return self.lin_self(x) + self.lin_neigh(neigh)


class GATLayer(nn.Module):
    """Gated neighbor blend (fast attention surrogate for ablation)."""

    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.lin = nn.Linear(in_dim, out_dim)
        self.gate = nn.Linear(out_dim * 2, 1)

    def forward(self, adj: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        h = self.lin(x)
        neigh = torch.sparse.mm(adj, h)
        deg = torch.sparse.sum(adj, dim=1).to_dense().clamp(min=1.0).unsqueeze(1)
        neigh = neigh / deg
        alpha = torch.sigmoid(self.gate(torch.cat([h, neigh], dim=1)))
        return alpha * h + (1.0 - alpha) * neigh


class GINLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, eps: float = 0.0):
        super().__init__()
        self.eps = eps
        self.mlp = nn.Sequential(nn.Linear(in_dim, out_dim), nn.ReLU(), nn.Linear(out_dim, out_dim))

    def forward(self, adj: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        neigh = torch.sparse.mm(adj, x)
        return self.mlp((1 + self.eps) * x + neigh)


class SurrogateModel(nn.Module):
    def __init__(self, arch: ArchName, in_dim: int, hidden: int = 32):
        super().__init__()
        self.arch = arch
        h2 = max(8, hidden // 2)
        if arch == "mlp":
            self.net = nn.Sequential(
                nn.Linear(in_dim, hidden),
                nn.ReLU(),
                nn.Linear(hidden, h2),
                nn.ReLU(),
                nn.Linear(h2, 1),
            )
        elif arch == "gcn":
            self.l1 = GCNLayer(in_dim, hidden)
            self.l2 = GCNLayer(hidden, h2)
            self.head = nn.Linear(h2, 1)
        elif arch == "graphsage":
            self.l1 = GraphSAGELayer(in_dim, hidden)
            self.l2 = GraphSAGELayer(hidden, h2)
            self.head = nn.Linear(h2, 1)
        elif arch == "gat":
            self.l1 = GATLayer(in_dim, hidden)
            self.l2 = GATLayer(hidden, h2)
            self.head = nn.Linear(h2, 1)
        elif arch == "gin":
            self.l1 = GINLayer(in_dim, hidden)
            self.l2 = GINLayer(hidden, h2)
            self.head = nn.Linear(h2, 1)
        else:
            raise ValueError(arch)

    def forward(self, adj: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        if self.arch == "mlp":
            return torch.sigmoid(self.net(x)).squeeze(-1)
        h = F.relu(self.l1(adj, x))
        h = F.relu(self.l2(adj, h))
        return torch.sigmoid(self.head(h)).squeeze(-1)


def train_architecture(
    arch: ArchName,
    adj: torch.Tensor,
    x: torch.Tensor,
    y: torch.Tensor,
    train_idx: torch.Tensor,
    test_idx: torch.Tensor,
    hidden: int = 32,
    epochs: int = 300,
    lr: float = 0.01,
    seed: int = 42,
) -> dict[str, float]:
    import numpy as np

    torch.manual_seed(seed)
    model = SurrogateModel(arch, x.shape[1], hidden)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        pred = model(adj, x)
        loss = loss_fn(pred[train_idx], y[train_idx])
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        pred = model(adj, x).numpy()
    y_np = y.numpy()
    y_test = y_np[test_idx.numpy()]
    p_test = pred[test_idx.numpy()]
    mae = float(np.abs(y_test - p_test).mean())
    ss_res = float(((y_test - p_test) ** 2).sum())
    ss_tot = float(((y_test - y_test.mean()) ** 2).sum())
    return {"mae": round(mae, 4), "r2": round(1 - ss_res / max(ss_tot, 1e-12), 4)}
