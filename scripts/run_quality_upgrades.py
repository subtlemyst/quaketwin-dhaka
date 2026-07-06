"""Run full quality-upgrade pipeline (hazard through resilience)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run QuakeTwin quality upgrades end-to-end")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip Open Buildings download")
    parser.add_argument("--skip-ensemble", action="store_true", help="Skip multi-scenario cascade (slow)")
    args = parser.parse_args()

    if not args.skip_fetch:
        import subprocess

        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts/fetch_open_buildings_heights.py")],
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            print("Open Buildings fetch skipped/failed; continuing with OSM heights.", flush=True)

    from quaketwin.pipeline import run_phase1_hazard  # noqa: E402
    from quaketwin.hazard.scenario import load_default_scenario  # noqa: E402
    from quaketwin.data.enrich import build_building_profiles  # noqa: E402
    from quaketwin.exposure.pipeline import run_diurnal_exposure  # noqa: E402
    from quaketwin.response.pipeline import run_response_model  # noqa: E402
    from quaketwin.cascade.ensemble import run_scenario_ensemble  # noqa: E402
    from quaketwin.cascade.gnn import train_cascade_gnn  # noqa: E402
    from quaketwin.cascade.gnn_ensemble import train_cascade_gnn_ensemble  # noqa: E402
    from quaketwin.resilience.pipeline import compute_resilience_index  # noqa: E402
    import json

    print("\n=== Phase 1 default hazard (logic-tree GMPE + Vs30) ===", flush=True)
    fc = run_phase1_hazard(scenario=load_default_scenario())
    out = ROOT / "data/processed/hazard_mw72_dauki.geojson"
    out.write_text(json.dumps(fc, indent=2), encoding="utf-8")

    print("\n=== Phase 2 building profiles ===", flush=True)
    build_building_profiles()

    print("\n=== Phase 3 diurnal exposure (HAZUS casualties) ===", flush=True)
    run_diurnal_exposure()

    print("\n=== Phase 4 response (network routing) ===", flush=True)
    run_response_model(period="midday")

    if not args.skip_ensemble:
        print("\n=== Phase 5 scenario ensemble ===", flush=True)
        run_scenario_ensemble(period="midday")
        print("\n=== Phase 5 cross-scenario GNN ===", flush=True)
        train_cascade_gnn_ensemble(period="midday")
    else:
        from quaketwin.cascade.simulate import run_cascade

        run_cascade(period="midday")
        train_cascade_gnn(period="midday")

    print("\n=== Resilience Index ===", flush=True)
    compute_resilience_index(period="midday")
    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
