# QuakeTwin Dhaka

**A graph-neural-network digital twin of earthquake vulnerability, dynamic population exposure, and cascading lifeline failure in Dhaka, Bangladesh**

Open, reproducible pipeline (Phases 0–5) with quality upgrades: GMPE logic-tree, Vs30 amplification, HAZUS casualties, network routing, multi-scenario cascade ensemble, physics-informed surrogate emulator, and Earthquake Resilience Index.

**Manuscript:** `paper/main.tex` (Elsevier CAS `cas-sc`)  
**Results:** `docs/results_summary.md`  
**Methods:** `docs/methodology.md`

## Research Question

> Can a building-resolved, cascade-aware digital twin assembled from open data support earthquake preparedness and emergency decision-making in a data-scarce megacity?

## Reference Scenario

| Parameter | Value |
|-----------|-------|
| ID | `dhaka_mw72_dauki` |
| Magnitude | Mw 7.2 |
| Fault | Dauki Fault Zone |
| Epicenter | 91.85°E, 24.35°N (~158 km from central Dhaka) |
| Exposure period | Midday (13:00) |
| Study area | 90.32–90.53°E, 23.68–23.95°N |

## Headline Results (Mw 7.2 Dauki, midday)

| Layer | Key metric |
|-------|------------|
| Hazard | Mean amplified PGA 0.224 g; MMI 8.08 |
| Buildings | 706,115 footprints; mean collapse p 0.40; 0.33% ≥ 0.5 |
| Exposure | 322,837 HAZUS-expected casualties; ~35k in high-risk buildings |
| Response | 243/728 hospitals overloaded; 7.2 min mean response time |
| Cascade | 4–7× lifeline amplification; 1.90× rescue-delay factor |
| Surrogate emulator | R² = 0.991 (single scenario); R² = 0.883 (cross-scenario) |
| ERI | Citywide 70.9 (very-high tier) |

See `docs/results_summary.md` for full tables and ensemble (Dauki vs Madhupur).

## Repository Structure

```
earthquake/
├── api/                         # FastAPI service
├── config/                      # dhaka.yaml, hazard_gmpe.yaml, scenarios.yaml, resilience.yaml, …
├── data/processed/              # Hazard, buildings, exposure, response, cascade, ERI outputs
├── docs/
│   ├── methodology.md           # Thesis chapter outline (aligned with paper)
│   └── results_summary.md       # Consolidated headline numbers
├── outputs/phase*/              # Publication figures and tables
├── paper/                       # CAS LaTeX manuscript + figures
├── scripts/                     # CLI pipelines
└── src/quaketwin/               # Core library
```

## Quick Start

### 1. Environment

```bash
cd earthquake
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev,geo,gnn]"
```

### 2. Full quality-upgrade pipeline

```bash
python scripts/run_quality_upgrades.py --skip-fetch
python scripts/publish_phase2.py
python scripts/publish_phase3.py
python scripts/publish_phase4.py
python scripts/publish_phase5.py
```

`--skip-fetch` skips the large Open Buildings height download (optional).

### 3. Individual phases

```bash
# Phase 1 — hazard (logic-tree GMPE + Vs30)
python scripts/run_hazard_scenario.py

# Phase 2 — building profiles + fragility
python scripts/build_building_profiles.py --format gpkg
python scripts/publish_phase2.py

# Phase 3 — diurnal exposure (HAZUS casualties)
python scripts/run_diurnal_exposure.py
python scripts/publish_phase3.py

# Phase 4 — response (network routing)
python scripts/run_response_model.py --period midday
python scripts/publish_phase4.py

# Phase 5 — cascade ensemble + surrogate emulator
python scripts/run_scenario_ensemble.py
python scripts/train_cascade_gnn_ensemble.py
python scripts/publish_phase5.py

# Resilience Index
python scripts/run_resilience_index.py

# Reviewer-response analyses (sensitivity, surrogate ablation, MC convergence)
python scripts/run_sensitivity_studies.py
python scripts/gnn_architecture_ablation.py
python scripts/mc_convergence_study.py
```

### 4. API

```bash
uvicorn api.main:app --reload
```

- Docs: http://127.0.0.1:8000/docs
- `GET /hazard/run`, `/exposure/diurnal`, `/response/summary`, `/cascade/summary`

### 5. Tests

```bash
pytest
```

## Phase Deliverables

| Phase | Key outputs |
|-------|-------------|
| 0 | Schema, config, data inventory |
| 1 | `hazard_mw72_dauki.geojson` — PGA, MMI, amplification, liquefaction |
| 2 | `dhaka_building_profiles.gpkg` — 706k buildings, collapse probability |
| 3 | `dhaka_exposure_diurnal.gpkg` — population + HAZUS casualties by hour |
| 4 | `dhaka_response_phase4.gpkg` — routing, hospital overload, rescue priority |
| 5 | Cascade nodes/zones, ensemble manifest, surrogate models, `outputs/phase5/` |
| ERI | `dhaka_resilience_index.gpkg`, `resilience_index_summary.json` |

Primary collapse field: **`collapse_probability`** (fragility). XGBoost `collapse_probability_ml` is sensitivity only.

## Optional: Open Buildings Heights

```bash
python scripts/fetch_open_buildings_heights.py   # streams S2 tile 375 (~3.5 GB)
python scripts/build_building_profiles.py
```

Requires disk space and time; OSM `building:levels` defaults apply if skipped.

## Paper

Compile `paper/main.tex` on Overleaf (see `paper/README.md`). Before submission:

- Repository: https://github.com/subtlemyst/quaketwin-dhaka
- Regenerate publication figures: `python scripts/regenerate_publication_figures.py`

## Next Steps (not implemented)

- **Phase 6:** CesiumJS 3D digital twin dashboard
- Improve road-graph connectivity for network routing (currently 5.9%)

## Citation

Document software version and data sources (OSM, WorldPop, USGS Vs30, regional hazard literature). See `paper/cas-refs.bib`.

## License

Academic / thesis use — add your institution's license as needed.
