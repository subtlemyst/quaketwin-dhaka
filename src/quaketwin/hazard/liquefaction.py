from __future__ import annotations

from quaketwin.geo.dhaka import soil_zone_properties


def compute_liquefaction_index(amplified_grid: list[dict]) -> list[dict]:
    """
    Liquefaction susceptibility index [0, 1] combining soil class and shaking.

    Based on simplified Iwasaki-style logic for thesis scaffold:
      L = base_susceptibility × shaking_factor × groundwater_proxy

    Groundwater proxy elevated in eastern lowlands (monsoon water table).
    Calibrate against Dhaka borehole literature in thesis validation.
    """
    from quaketwin.hazard.site import vs30_liquefaction_susceptibility

    results = []
    for cell in amplified_grid:
        zone = cell["soil_zone"]
        if "vs30" in cell:
            base = vs30_liquefaction_susceptibility(cell["vs30"])
        else:
            props = soil_zone_properties(zone)
            base = props["liquefaction_susceptibility"]

        # Shaking factor: PGA > 0.1g increases susceptibility
        pga = cell["amplified_pga_g"]
        shaking_factor = min(1.0, max(0.2, (pga - 0.05) / 0.35))

        # Groundwater proxy by zone
        gw_proxy = {
            "marsh_organic": 1.0,
            "holocene_alluvium": 0.85,
            "engineered_fill": 0.7,
            "pleistocene_terrace": 0.45,
        }.get(zone, 0.7)

        liq_index = min(1.0, base * shaking_factor * gw_proxy)

        results.append(
            {
                **cell,
                "liquefaction_index": liq_index,
                "liquefaction_class": _classify(liq_index),
            }
        )
    return results


def _classify(index: float) -> str:
    if index >= 0.7:
        return "high"
    if index >= 0.4:
        return "moderate"
    if index >= 0.15:
        return "low"
    return "very_low"
