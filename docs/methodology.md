# QuakeTwin Dhaka — Methodology Outline (Thesis)

This document maps repository components to thesis chapters and is aligned with
the Elsevier CAS manuscript (`paper/main.tex`) and consolidated results
(`docs/results_summary.md`). Adapt section numbers to your department template.

**Reference scenario:** Mw 7.2, Dauki Fault (`dhaka_mw72_dauki`), midday exposure.

---

## Chapter 1 — Introduction

- **Problem:** Dhaka's seismic risk, data-poor building stock, cascading infrastructure failures
- **Research question:** (see README)
- **Contributions (implemented):**
  1. GMPE logic-tree ground motion with Vs30 site amplification and liquefaction susceptibility
  2. Building-resolved fragility for 706,115 OSM footprints (WorldPop + plausibility caps)
  3. Population-conserving diurnal exposure with HAZUS severity-stratified casualties
  4. Emergency-response model with network shortest-path routing and hospital overload
  5. Six-scenario lifeline cascade ensemble (Dauki + Madhupur) with physics-informed surrogate emulator
  6. Composite Earthquake Resilience Index (ERI) over building zones

## Chapter 2 — Literature Review

Suggested subsections:

- Seismic hazard in Bangladesh (Dauki, Madhupur, subduction)
- Dhaka basin geotechnical characteristics and liquefaction case studies
- Building vulnerability in developing megacities
- Digital twins and graph-based infrastructure modeling
- Gap: integrated cascade + response optimization for data-scarce megacities

## Chapter 3 — Study Area and Data (Phase 0)

### 3.1 Geographic extent

- Bounding box: `config/dhaka.yaml` → `study_area.bbox`
- Greater Dhaka: 90.32–90.53°E, 23.68–23.95°N

### 3.2 Data sources

| Layer | Primary source | Count / status |
|-------|----------------|----------------|
| Building footprints | OSM (Geofabrik Bangladesh) | 706,115 polygons |
| Roads | OSM | highway-tagged ways |
| Hospitals / clinics | OSM | 728 facilities |
| Power nodes | OSM `power=*` | 61 |
| Communication towers | OSM | 8 (under-mapped) |
| Highway bridges | OSM `bridge=yes` | 1,195 |
| Population | WorldPop 2020 constrained | ~100 m grid |
| Vs30 | USGS Vs30 raster | `data/raw/vs30/usgs_vs30_dhaka.tif` |
| Soil zones | Literature-informed proxy | 3 classes |
| Building heights (optional) | Google Open Buildings v3 | `scripts/fetch_open_buildings_heights.py` |

Inventory API: `GET /data-inventory` or `quaketwin.schema.inventory.inventory_summary()`.

### 3.3 Digital twin graph schema

- Relational schema: `data/schema/dhaka_graph.sql`
- Cascade dependency graph: 2,479 nodes, 9,737 edges (Phase 5)

### 3.4 Building profile framework

- Fields: `src/quaketwin/schema/building.py`, enriched in `src/quaketwin/data/enrich.py`
- Primary output: `data/processed/dhaka_building_profiles.gpkg`

## Chapter 4 — Earthquake Scenario Design

### 4.1 Fault models

- **Dauki Fault Zone** (reference): `config/dhaka.yaml` → `faults.dauki`
- **Madhupur Fault** (ensemble / generalization): `faults.madhupur`

### 4.2 Scenario parameters

| Parameter | API field | Default (reference) |
|-----------|-----------|---------------------|
| Magnitude | `magnitude` | 7.2 |
| Epicenter | `epicenter_lon`, `epicenter_lat` | 91.85, 24.35 |
| Depth | `depth_km` | 15 |
| Time of day | `time_of_day` / `period` | midday (13:00) |

### 4.3 Scenario ensemble (Phase 5 upgrade)

`config/scenarios.yaml` — four Dauki magnitudes (train) + two Madhupur magnitudes (test):

| Scenario ID | Fault | Mw |
|-------------|-------|-----|
| `dhaka_mw68_dauki` | Dauki | 6.8 |
| `dhaka_mw70_dauki` | Dauki | 7.0 |
| `dhaka_mw72_dauki` | Dauki | 7.2 |
| `dhaka_mw75_dauki` | Dauki | 7.5 |
| `dhaka_mw65_madhupur` | Madhupur | 6.5 |
| `dhaka_mw70_madhupur` | Madhupur | 7.0 |

Implementation: `src/quaketwin/hazard/scenario.py`, `src/quaketwin/cascade/ensemble.py`.

## Chapter 5 — Hazard Modeling (Phase 1)

### 5.1 Ground motion prediction (GMPE logic-tree)

- Module: `src/quaketwin/hazard/ground_motion.py`
- Configuration: `config/hazard_gmpe.yaml`
- **Weighted logic-tree:** 55% calibrated Boore-style + 45% Atkinson–Boore 2006 crustal
- Outputs: bedrock PGA (g), MMI

**Reference scenario results** (Mw 7.2 Dauki):

| Quantity | Value |
|----------|-------|
| Bedrock PGA (mean) | 0.161 g |
| Amplified PGA (mean) | 0.224 g |
| MMI (mean) | 8.08 |

### 5.2 Site amplification (Vs30 + soil zones)

- Vs30 raster sampling: `src/quaketwin/hazard/site.py`
- Raster: `data/raw/vs30/usgs_vs30_dhaka.tif` (180–375 m/s)
- Soil-proxy zones: `src/quaketwin/hazard/amplification.py`

### 5.3 Liquefaction susceptibility

- Module: `src/quaketwin/hazard/liquefaction.py`
- Index range [0, 1]; used as fragility boost (capped at 0.20)

### 5.4 Pipeline and outputs

```bash
python scripts/run_hazard_scenario.py
# or full upgrade:
python scripts/run_quality_upgrades.py --skip-fetch
```

Output: `data/processed/hazard_mw72_dauki.geojson` (grid properties: `pga_g`, `mmi`, `amplified_pga_g`, `soil_zone_code`, `liquefaction_index`).

### 5.5 Map figures

`outputs/phase2/figures/` — F5.1 (bedrock PGA), F5.2 (amplified PGA), F5.3 (liquefaction), F5.4 (PGA–distance profile).

## Chapter 6 — Building Vulnerability (Phase 2)

### 6.1 Building footprint ingestion

- Source: `data/processed/dhaka_buildings.geojson` (706,115 footprints)
- Extract: `python scripts/extract_dhaka_osm.py --layer buildings`

### 6.2 Attribute enrichment

| Attribute | Method | Module |
|-----------|--------|--------|
| `construction_type` | OSM `building=*` taxonomy | `data/attributes.py` |
| `height_m` | `building:levels` × 3 m, Open Buildings snap, or default | `data/attributes.py`, `data/heights.py` |
| `occupancy_type` | OSM building + amenity tags | `data/attributes.py` |
| `population_est` | WorldPop × footprint, capped (20,000 m², structural capacity) | `data/enrich.py` |
| Hazard fields | Nearest grid join | `data/enrich.py` |
| `dist_fault_km` | Haversine to fault reference | `data/enrich.py` |

```bash
python scripts/build_building_profiles.py --format gpkg
python scripts/publish_phase2.py
```

### 6.3 Collapse probability model

**Primary model:** HAZUS-inspired logistic fragility (`src/quaketwin/risk/fragility.py`).

**Reference scenario results:**

| Metric | Value |
|--------|-------|
| Mean collapse probability | 0.398 |
| Buildings with p ≥ 0.5 | 2,323 (0.33%) |
| Total population (static) | 4,531,511 |

Fragility ordering: informal (0.657) > unknown (0.401) > residential (0.359) > … > RC (0.141).

**Sensitivity only:** XGBoost `collapse_probability_ml` — not used in primary maps.

### 6.4 Publication bundle

`outputs/phase2/` — tables T6.1–T6.6, figures F5.1–F6.3, `publish_manifest.json`.

## Chapter 7 — Validation

### 7.1 GMPE plausibility

`publish_manifest.json` → `hazard_validation.benchmark_checks` — both pass:

- Bedrock PGA mean 0.161 g within 0.06–0.25 g (Mw 7.0–7.5, 100–200 km)
- MMI mean 8.08 within 6.0–8.5

### 7.2 Building layer validation

- Risk spread physically sensible by construction class
- Dominant uncertainty: 95% of buildings lack OSM construction tags (default to "unknown")
- High-risk threshold (p ≥ 0.5): only 0.33% under logic-tree + Vs30 — narrate as moderate-band dominance, not pre-upgrade 51.8%

### 7.3 Sensitivity

- Scenario ensemble: magnitude and fault proximity (Dauki vs Madhupur)
- Cross-scenario GNN generalization to held-out Madhupur graphs

## Chapter 8 — Dynamic Population Exposure (Phase 3)

### 8.1 Motivation

WorldPop is a nighttime residential surface. Exposure varies by hour via occupancy multipliers with **population conservation**.

### 8.2 Diurnal model + HAZUS casualties

Configuration: `config/diurnal_exposure.yaml`

```
raw_t        = population_est × occupancy_multiplier[period][occupancy_type]
scale_t      = Σ population_est / Σ raw_t
population_at_time = raw_t × scale_t
expected_casualties = HAZUS_severity_rates(population_at_time, collapse_probability, construction_type)
```

Casualty module: `src/quaketwin/exposure/casualties.py` (`hazus_severity_stratified`).

```bash
python scripts/run_diurnal_exposure.py
python scripts/publish_phase3.py
```

**Reference results (midday):** 4,593,956 population, 35,210 in high-risk buildings, **322,837 expected casualties**.

### 8.3 Thesis claim

> Under population conservation, diurnal variation in casualties is ~1–2% with current OSM occupancy tags. High-risk exposure is small (~35k people in p ≥ 0.5 buildings) because the upgraded hazard model places most stock in the moderate band.

## Chapter 9 — Emergency Response (Phase 4)

### 9.1 Inputs

- `data/processed/dhaka_exposure_diurnal.gpkg`
- `data/processed/dhaka_roads.geojson`
- `data/processed/dhaka_hospitals.geojson`
- `config/response.yaml`

### 9.2 Response model (network routing)

Module: `src/quaketwin/response/routing.py` — Dijkstra shortest path on the largest road-graph component where connected; straight-line fallback otherwise.

```bash
python scripts/run_response_model.py --period midday
python scripts/publish_phase4.py
```

**Reference results (midday):**

| Metric | Value |
|--------|-------|
| Expected casualties routed | 322,837 |
| Mean response time | 7.2 min |
| Network-routed buildings | 5.9% |
| Overloaded hospitals | 243 / 728 (33%) |
| Max overload ratio | 38× |

### 9.3 Rescue priority

```
priority = 0.65 × normalized_casualties + 0.20 × collapse_probability + 0.15 × normalized_access_score
```

### 9.4 Limitations

- Only 5.9% of buildings connect via the road graph; most use straight-line fallback
- Hospital capacities are OSM-amenity estimates

## Chapter 10 — Infrastructure Cascade (Phase 5)

### 10.1 Dependency graph

2,479 nodes, 9,737 edges — power (61), comm towers (8), bridges (1,195), hospitals (728), zones (487).

Configuration: `config/cascade.yaml`.

### 10.2 Monte Carlo cascade (reference: Mw 7.2 Dauki, 300 iterations)

| Node type | Direct | Total | Amplification |
|-----------|--------|-------|---------------|
| Power | 0.139 | 0.600 | 4.3× |
| Comm tower | 0.127 | 0.766 | 6.0× |
| Hospital | 0.085 | 0.604 | 7.1× |
| Bridge | 0.069 | 0.068 | 1.0× |

Population-weighted: 67% power loss, 68% comm loss, delay factor **1.90×**.

### 10.3 Scenario ensemble

```bash
python scripts/run_scenario_ensemble.py
# or:
python scripts/run_quality_upgrades.py --skip-fetch
```

Manifest: `data/processed/cascade_ensemble_manifest.json`.

**Key finding:** Mw 7.0 Madhupur (closer) → 100% comm loss, 2.34× delay vs Mw 7.2 Dauki (68% comm, 1.90×).

### 10.4 Physics-informed surrogate emulator

The GCN is a **surrogate emulator** trained on Monte Carlo cascade labels; production inference uses **GraphSAGE** (lowest ablation MAE). It accelerates the physics simulation for interactive queries and does not replace the cascade model.

| Model | Evaluation | MAE | R² |
|-------|------------|-----|-----|
| Single-scenario GraphSAGE | 75/25 node hold-out (Mw 7.2) | 0.016 | 0.992 |
| Cross-scenario GraphSAGE | Held-out Madhupur scenarios | 0.078 | 0.883 |

```bash
python scripts/train_cascade_gnn.py              # single scenario
python scripts/train_cascade_gnn_ensemble.py     # cross-scenario
python scripts/publish_phase5.py
```

Artifacts: `data/models/cascade_gnn.pt`, `data/models/cascade_gnn_ensemble.pt`, metrics JSON files.

### 10.5 Earthquake Resilience Index (ERI)

Module: `src/quaketwin/resilience/pipeline.py`, config: `config/resilience.yaml`.

Weighted components: structural (0.30), emergency capacity (0.25), lifeline robustness (0.25), accessibility (0.20).

```bash
python scripts/run_resilience_index.py
```

**Reference:** citywide ERI **70.9**; 252 very-high + 235 high zones. Output: `data/processed/dhaka_resilience_index.gpkg`.

### 10.6 Publication outputs

`outputs/phase5/` — F9.1–F9.4, T9.1–T9.3.

## Chapter 11 — Discussion and Policy Implications

Align with `paper/main.tex` Discussion:

1. Retrofit priority in eastern/riverine soft-soil zones (amplification + liquefaction + cascade delay)
2. Nearest-hospital routing insufficient — pre-position field hospitals
3. Substation hardening and hospital backup power as cost-effective cascade interventions
4. Madhupur proximity stress-test — planners need multi-epicenter scenarios
5. Cross-scenario GNN enables interactive epicenter sweeps at millisecond latency

## Chapter 12 — Conclusion and Future Work

- Implemented: Phases 0–5, quality upgrades, ERI, CAS manuscript (`paper/`)
- Future: CesiumJS 3D dashboard (Phase 6), full road-graph connectivity, Open Buildings heights merge, authoritative utility/geotechnical data

---

## Reproducibility Checklist

- [ ] Pin Python version in thesis appendix
- [ ] Archive `config/` version and Git commit hash per experiment
- [ ] Document `pip freeze` or lockfile in supplementary materials
- [ ] Replace `\githubrepo` placeholder in `paper/main.tex` before submission

## Full pipeline (quality upgrades)

```bash
python scripts/run_quality_upgrades.py --skip-fetch
python scripts/publish_phase2.py
python scripts/publish_phase3.py
python scripts/publish_phase4.py
python scripts/publish_phase5.py
```

Headline numbers: `docs/results_summary.md`. Manuscript: `paper/main.tex`.
