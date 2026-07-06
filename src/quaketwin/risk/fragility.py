"""HAZUS-inspired fragility stubs for collapse probability (Phase 2)."""

from __future__ import annotations

import math

# Median collapse capacity as amplified PGA (g) by construction class — thesis scaffold
_MEDIAN_CAPACITY_G: dict[str, float] = {
    "rc": 0.45,
    "commercial": 0.40,
    "institutional": 0.38,
    "industrial": 0.35,
    "residential": 0.30,
    "masonry": 0.25,
    "wood": 0.20,
    "informal": 0.18,
    "unknown": 0.28,
}

_LOGISTIC_K = 10.0


def collapse_probability(
    amplified_pga_g: float,
    construction_type: str,
    liquefaction_index: float = 0.0,
    height_m: float = 6.0,
) -> float:
    """
    Estimate P(collapse) using logistic fragility around class median capacity.

    Replace with calibrated ML model (XGBoost) after label validation.
    """
    median = _MEDIAN_CAPACITY_G.get(construction_type, 0.28)
    # Taller buildings slightly more vulnerable (soft-story proxy)
    median -= min(0.08, max(0, (height_m - 12) * 0.004))

    x = amplified_pga_g - median
    base = 1.0 / (1.0 + math.exp(-_LOGISTIC_K * x))
    liq_boost = min(0.20, liquefaction_index * 0.25)
    return round(min(1.0, max(0.0, base + liq_boost)), 4)


def fire_probability(
    collapse_probability: float,
    occupancy_type: str,
    liquefaction_index: float = 0.0,
) -> float:
    """Post-collapse fire risk proxy."""
    occ_factor = {
        "industrial": 0.15,
        "commercial": 0.10,
        "residential": 0.06,
        "healthcare": 0.08,
    }.get(occupancy_type, 0.05)
    return round(min(1.0, collapse_probability * 0.4 + occ_factor + liquefaction_index * 0.05), 4)
