"""HAZUS-inspired severity-stratified casualty rates (Phase 3 upgrade)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# Expected affected-person rate by collapse probability band and occupancy.
# Collapse bands approximate HAZUS damage states DS4+ (complete/partial collapse).
# Rates are injury + fatality + entrapment proxies, not fatality-only.
_DEFAULT_RATES: dict[str, dict[str, float]] = {
    "residential": {"partial": 0.22, "severe": 0.38},
    "commercial": {"partial": 0.18, "severe": 0.32},
    "education": {"partial": 0.25, "severe": 0.42},
    "industrial": {"partial": 0.15, "severe": 0.28},
    "healthcare": {"partial": 0.20, "severe": 0.35},
    "assembly": {"partial": 0.28, "severe": 0.45},
    "storage": {"partial": 0.08, "severe": 0.15},
}


def load_casualty_rates(cfg: dict[str, Any]) -> dict[str, dict[str, float]]:
    model = cfg.get("casualty_model", {})
    if "severity_rates" in model:
        return model["severity_rates"]
    return _DEFAULT_RATES


def expected_casualties_vectorized(
    population: np.ndarray,
    collapse_p: np.ndarray,
    occupancy: pd.Series,
    rates: dict[str, dict[str, float]],
) -> np.ndarray:
    """
    E[affected] = pop * P(collapse) * rate(occupancy, severity band).

    Severity band is inferred from collapse probability:
    partial collapse proxy: 0.35 <= p < 0.65; severe: p >= 0.65.
    """
    occ = occupancy.fillna("residential").astype(str)
    partial_rate = occ.map(lambda o: rates.get(o, rates["residential"])["partial"]).to_numpy(dtype=float)
    severe_rate = occ.map(lambda o: rates.get(o, rates["residential"])["severe"]).to_numpy(dtype=float)

    band_rate = np.where(collapse_p >= 0.65, severe_rate, partial_rate)
    band_rate = np.where(collapse_p < 0.35, partial_rate * 0.65, band_rate)

    return np.round(population * collapse_p * band_rate).astype(np.int32)
