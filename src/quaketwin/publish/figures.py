"""Generate thesis figure PNGs for Phase 1–2."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from quaketwin.config import ProjectSettings, load_config
from quaketwin.geo.dhaka import haversine_km
from quaketwin.hazard.scenario import load_default_scenario

from quaketwin.publish.style import apply_publication_style, save_publication_figure


def _apply_pub_style() -> None:
    apply_publication_style()


def _save_fig(fig, path: Path) -> Path:
    save_publication_figure(fig, path)
    return path.with_suffix(".png")


def _setup_ax(ax, title: str, xlabel: str = "Longitude", ylabel: str = "Latitude") -> None:
    ax.set_title(title, fontsize=13)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_aspect("equal")


def figure_hazard_maps(out_dir: Path) -> list[Path]:
    """F5.1–F5.3 hazard layers from Phase 1 GeoJSON."""
    root = ProjectSettings().project_root
    hazard_path = root / "data/processed/hazard_mw72_dauki.geojson"
    with open(hazard_path, encoding="utf-8") as f:
        fc = json.load(f)

    lons = [feat["geometry"]["coordinates"][0] for feat in fc["features"]]
    lats = [feat["geometry"]["coordinates"][1] for feat in fc["features"]]
    pga = [feat["properties"]["pga_g"] for feat in fc["features"]]
    amp = [feat["properties"]["amplified_pga_g"] for feat in fc["features"]]
    liq = [feat["properties"]["liquefaction_index"] for feat in fc["features"]]

    layers = [
        ("F5_1_bedrock_pga.png", pga, "Bedrock PGA (g) — Mw 7.2 Dauki", "YlOrRd"),
        ("F5_2_amplified_pga.png", amp, "Amplified PGA (g) — Mw 7.2 Dauki", "YlOrRd"),
        ("F5_3_liquefaction.png", liq, "Liquefaction susceptibility index", "Blues"),
    ]

    written = []
    _apply_pub_style()
    for fname, values, title, cmap in layers:
        fig, ax = plt.subplots(figsize=(8, 7))
        sc = ax.scatter(lons, lats, c=values, cmap=cmap, s=12, edgecolors="none")
        plt.colorbar(sc, ax=ax, shrink=0.8)
        _setup_ax(ax, title)
        path = out_dir / fname
        fig.tight_layout()
        _save_fig(fig, path)
        plt.close(fig)
        written.append(path.with_suffix(".png"))
    return written


def figure_pga_distance_profile(out_dir: Path) -> Path:
    """F5.4 PGA vs distance cross-section from epicenter through Dhaka."""
    scenario = load_default_scenario()
    cfg = load_config()
    center = cfg["study_area"]["center"]
    epic = cfg["faults"]["dauki"]["reference_epicenter"]

    n = 40
    lons = np.linspace(center["lon"], epic["lon"], n)
    lats = np.linspace(center["lat"], epic["lat"], n)
    from quaketwin.hazard.ground_motion import compute_ground_motion_grid

    grid = [{"lon": float(lo), "lat": float(la)} for lo, la in zip(lons, lats)]
    result = compute_ground_motion_grid(grid, scenario)
    dists = [
        haversine_km(epic["lon"], epic["lat"], r["lon"], r["lat"]) for r in result
    ]
    pgas = [r["pga_g"] for r in result]

    _apply_pub_style()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(dists, pgas, "o-", color="#c0392b", linewidth=2, markersize=4)
    ax.axvline(
        haversine_km(epic["lon"], epic["lat"], center["lon"], center["lat"]),
        color="gray",
        linestyle="--",
        label="Dhaka center",
    )
    ax.set_xlabel("Distance from epicenter (km)")
    ax.set_ylabel("Bedrock PGA (g)")
    ax.set_title("F5.4 — PGA attenuation toward Dauki epicenter")
    ax.legend()
    ax.grid(True, alpha=0.3)
    path = out_dir / "F5_4_pga_distance_profile.png"
    fig.tight_layout()
    _save_fig(fig, path)
    plt.close(fig)
    return path


def figure_collapse_maps(out_dir: Path, profiles_path: Path, sample_n: int = 80_000) -> list[Path]:
    """F6.1–F6.2 building collapse risk figures."""
    gdf = gpd.read_file(profiles_path)
    if len(gdf) > sample_n:
        gdf = gdf.sample(n=sample_n, random_state=42)

    written = []
    _apply_pub_style()

    fig, ax = plt.subplots(figsize=(8, 7))
    sc = ax.scatter(
        gdf["lon"],
        gdf["lat"],
        c=gdf["collapse_probability"],
        cmap="RdYlGn_r",
        s=0.3,
        vmin=0,
        vmax=1,
        alpha=0.6,
    )
    plt.colorbar(sc, ax=ax, label="P(collapse)", shrink=0.8)
    _setup_ax(ax, "F6.1 — Building collapse probability (Mw 7.2 Dauki)")
    path = out_dir / "F6_1_collapse_probability_map.png"
    fig.tight_layout()
    _save_fig(fig, path)
    plt.close(fig)
    written.append(path.with_suffix(".png"))

    by_type = (
        gdf.groupby("construction_type")["collapse_probability"]
        .mean()
        .sort_values(ascending=True)
        .tail(12)
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    by_type.plot(kind="barh", ax=ax, color="#8e44ad")
    ax.set_xlabel("Mean collapse probability")
    ax.set_title("F6.2 — Mean collapse risk by construction type")
    ax.set_xlim(0, 1)
    path = out_dir / "F6_2_collapse_by_construction_type.png"
    fig.tight_layout()
    _save_fig(fig, path)
    plt.close(fig)
    written.append(path.with_suffix(".png"))

    fig, ax = plt.subplots(figsize=(6, 5))
    hb = ax.hexbin(
        gdf["liquefaction_index"],
        gdf["collapse_probability"],
        gridsize=40,
        cmap="magma",
        mincnt=1,
    )
    plt.colorbar(hb, ax=ax, label="Building count")
    ax.set_xlabel("Liquefaction index")
    ax.set_ylabel("Collapse probability")
    ax.set_title("F6.3 — Liquefaction vs collapse risk")
    path = out_dir / "F6_3_liquefaction_vs_collapse.png"
    fig.tight_layout()
    _save_fig(fig, path)
    plt.close(fig)
    written.append(path)

    return written


def generate_all_figures(out_dir: Path, profiles_path: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    paths.extend(figure_hazard_maps(out_dir))
    paths.append(figure_pga_distance_profile(out_dir))
    paths.extend(figure_collapse_maps(out_dir, profiles_path))
    return paths
