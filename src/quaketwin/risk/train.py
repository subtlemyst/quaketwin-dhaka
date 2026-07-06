"""Train XGBoost collapse model on enriched building profiles (Phase 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

from quaketwin.config import ProjectSettings
from quaketwin.risk.fragility import collapse_probability as fragility_collapse


_CONSTRUCTION_CODES = {
    "rc": 0,
    "commercial": 1,
    "institutional": 2,
    "industrial": 3,
    "residential": 4,
    "masonry": 5,
    "wood": 6,
    "informal": 7,
    "unknown": 8,
}


def _default_paths() -> dict[str, Path]:
    root = ProjectSettings().project_root
    return {
        "profiles": root / "data/processed/dhaka_building_profiles.gpkg",
        "model": root / "data/processed/collapse_model.json",
        "metrics": root / "data/processed/collapse_model_metrics.json",
        "output": root / "data/processed/dhaka_building_profiles_scored.gpkg",
    }


def _make_labels(df: pd.DataFrame) -> pd.Series:
    """Fragility-derived labels for supervised training (replace with survey data if available)."""
    return df.apply(
        lambda r: fragility_collapse(
            r["amplified_pga_g"], r["construction_type"], r["liquefaction_index"], r["height_m"]
        ),
        axis=1,
    )


def _feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "construction_code": df["construction_type"].map(_CONSTRUCTION_CODES).fillna(8).astype(int),
            "height_m": df["height_m"].astype(float),
            "amplified_pga_g": df["amplified_pga_g"].astype(float),
            "liquefaction_index": df["liquefaction_index"].astype(float),
            "footprint_m2": df["footprint_m2"].astype(float),
            "dist_fault_km": df["dist_fault_km"].astype(float),
            "population_est": df["population_est"].astype(float),
        }
    )


def train_collapse_model(
    profiles_path: Path | None = None,
    sample_n: int | None = 100_000,
    test_fraction: float = 0.2,
) -> dict[str, Any]:
    """
    Train XGBoost regressor for collapse probability.

    Uses spatial split by longitude tile to reduce spatial leakage.
  """
    try:
        import xgboost as xgb
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        raise ImportError("Install phase2 ML deps: pip install -e '.[ml]'") from e

    paths = _default_paths()
    profiles_path = profiles_path or paths["profiles"]
    print(f"Loading {profiles_path}", flush=True)
    gdf = gpd.read_file(profiles_path)
    if sample_n and len(gdf) > sample_n:
        gdf = gdf.sample(n=sample_n, random_state=42)
        print(f"  sampled {sample_n:,} buildings for training", flush=True)

    df = pd.DataFrame(gdf.drop(columns="geometry"))
    X = _feature_matrix(df)
    y = _make_labels(df)

    # Spatial split: train on west tiles, test on east
    split_lon = df["lon"].quantile(1 - test_fraction)
    train_mask = df["lon"] < split_lon
    X_train, X_test = X[train_mask], X[~train_mask]
    y_train, y_test = y[train_mask], y[~train_mask]

    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    print("Training XGBoost...", flush=True)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    pred_test = np.clip(model.predict(X_test), 0, 1)
    metrics = {
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "mae": round(float(mean_absolute_error(y_test, pred_test)), 4),
        "r2": round(float(r2_score(y_test, pred_test)), 4),
        "mean_label": round(float(y.mean()), 4),
        "mean_pred": round(float(pred_test.mean()), 4),
        "primary_model": "fragility",
        "note": (
            "XGBoost is sensitivity analysis only; thesis uses fragility collapse_probability. "
            "Negative R2 indicates ML does not outperform the rule-based label generator — "
            "expected when labels are derived from the same hazard features."
        ),
    }

    paths["model"].parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(paths["model"]))
    paths["metrics"].write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2), flush=True)

    # Score full dataset if we trained on sample
    if sample_n and len(gpd.read_file(profiles_path)) > sample_n:
        print("Scoring full building layer...", flush=True)
        full = gpd.read_file(profiles_path)
        full_df = pd.DataFrame(full.drop(columns="geometry"))
        preds = np.clip(model.predict(_feature_matrix(full_df)), 0, 1)
        full["collapse_probability_ml"] = preds.round(4)
        # Primary thesis field remains fragility-based
        full["collapse_probability"] = full_df.apply(
            lambda r: fragility_collapse(
                r["amplified_pga_g"], r["construction_type"], r["liquefaction_index"], r["height_m"]
            ),
            axis=1,
        )
        full.to_file(paths["output"], driver="GPKG", layer="building_profiles_scored")
        metrics["full_output"] = str(paths["output"])
    else:
        gdf["collapse_probability_ml"] = np.clip(model.predict(X), 0, 1).round(4)
        gdf["collapse_probability"] = y.round(4)
        gdf.to_file(paths["output"], driver="GPKG", layer="building_profiles_scored")
        metrics["full_output"] = str(paths["output"])

    return metrics
