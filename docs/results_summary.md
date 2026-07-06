# QuakeTwin Dhaka — Consolidated Results Summary

Aligned with `paper/main.tex` and `docs/methodology.md`.

Scenario: **Mw 7.2, Dauki fault**, epicenter ~158 km from central Dhaka.
All numbers below come from the **quality-upgrade pipeline**
(`scripts/run_quality_upgrades.py`): GMPE logic-tree, Vs30 site amplification,
HAZUS severity-stratified casualties, network shortest-path routing (where
connected), six-scenario cascade ensemble, physics-informed surrogate emulator, and composite
Earthquake Resilience Index (ERI).

Source manifests: `outputs/phase2/publish_manifest.json`,
`outputs/phase3/publish_manifest.json`, `outputs/phase4/publish_manifest.json`,
`data/processed/cascade_ensemble_manifest.json`,
`data/models/cascade_gnn_ensemble_metrics.json`,
`data/processed/resilience_index_summary.json`.

---

## 1. Hazard (Phase 1 → thesis Chapter 5)

| Quantity | Value |
|---|---|
| Bedrock PGA (min / mean / max) | 0.145 / 0.161 / 0.178 g |
| Soil-amplified PGA (min / mean / max) | 0.188 / 0.224 / 0.252 g |
| MMI (mean) | 8.08 (range 7.99–8.17) |

Upgrades applied:

- **GMPE logic-tree** (`config/hazard_gmpe.yaml`): weighted mean of calibrated
  Boore-style (55%) and Atkinson–Boore 2006 crustal (45%) relations.
- **Vs30 site amplification** (`data/raw/vs30/usgs_vs30_dhaka.tif`): building-level
  sampling from the USGS Vs30 raster (180–375 m/s over the study area).

Both literature benchmark checks pass:

- Bedrock PGA at 150–200 km from an Mw 7.0–7.5 crustal event — expected
  0.06–0.25 g, model mean 0.161 g.
- Expected MMI in Greater Dhaka for a large eastern-fault event — expected
  6.0–8.5, model mean 8.08.

Compared with the pre-upgrade single-relation model, mean amplified PGA fell
from 0.238 g to 0.224 g, which propagates to lower mean collapse probability
(Section 2).

Figures: F5.1–F5.4. Tables: T6.1–T6.2.

## 2. Building vulnerability (Phase 2 → thesis Chapter 6)

706,115 OSM building footprints, estimated static population **4,531,511**
(WorldPop 2020, constrained, with per-building plausibility caps).

| Risk class (collapse probability) | Buildings |
|---|---|
| Low (< 0.2) | 5,588 |
| Moderate (0.2–0.5) | 698,204 |
| High (≥ 0.5) | 2,323 |

- Mean collapse probability: **0.398** (median 0.401)
- Buildings with collapse probability ≥ 0.5: **2,323 (0.33%)**

By construction type (mean collapse probability):

| Type | Count | Mean collapse p |
|---|---|---|
| Informal | 176 | 0.657 |
| Unknown (untagged OSM) | 673,392 | 0.401 |
| Residential (tagged) | 26,374 | 0.359 |
| Industrial | 415 | 0.267 |
| Institutional | 890 | 0.223 |
| Commercial | 1,553 | 0.200 |
| Reinforced concrete | 3,315 | 0.141 |

The ordering remains physically sensible. The GMPE logic-tree and Vs30
amplification shift most buildings into the moderate band (0.2–0.5); only
0.33% exceed the 0.5 “high-risk” threshold. This is a defensible consequence
of the upgraded hazard model, not a data bug — but it changes how “high-risk
exposure” should be narrated (see Section 3).

Figures: F6.1–F6.3. Tables: T6.3–T6.6.

## 3. Diurnal exposure (Phase 3 → thesis Chapter 8)

Population-conserving redistribution; casualties use **HAZUS
severity-stratified rates** (`casualty_model: hazus_severity_stratified`) rather
than the legacy flat 35% proxy.

| Period | Total population | In high-risk buildings (p≥0.5) | Expected casualties |
|---|---|---|---|
| 00:00 midnight | 4,475,588 | 35,038 | 328,634 |
| 08:00 morning commute | 4,586,032 | 35,093 | 326,843 |
| 13:00 midday | 4,593,956 | 35,210 | **322,837** |
| 18:00 evening | 4,542,278 | 34,903 | 327,568 |

Honest findings to report:

1. **High-risk building stock is small** under the upgraded hazard model (~35k
   people in buildings with collapse p ≥ 0.5 at any hour). Diurnal variation in
   high-risk exposure is ~1% — occupancy shifts matter little when so few
   buildings cross the threshold.
2. **Expected casualties (~0.32 M at midday)** are lower than the legacy flat
   35% estimate (~0.75 M) because HAZUS severity rates are lower on average and
   mean collapse probability is lower.
3. Casualty totals vary by ~1% across the day; flatness still reflects OSM
   occupancy-tag incompleteness (~95% residential default).

Figures: F7.1/F7.3. Table: T7.1.

## 4. Emergency response (Phase 4 → thesis Chapter 9)

Midday scenario, 728 OSM hospitals/clinics; **network shortest-path routing**
where the road graph connects building to facility (fallback to straight-line
otherwise).

| Quantity | Value |
|---|---|
| Total expected casualties routed | 322,837 |
| Mean response-time proxy | **7.2 min** |
| Buildings with network-routed paths | **5.9%** |
| Hospitals over emergency capacity | **243 of 728 (33%)** |
| Worst overload ratio | **38×** capacity |

Network routing reduces mean response time versus straight-line proxies (8.7 min
pre-upgrade) but coverage is limited by OSM road-graph connectivity — a key
limitation to state.

Figures: F8.1–F8.3. Tables: T8.1–T8.2.

## 5. Infrastructure cascade (Phase 5 → thesis Chapter 10)

**Reference scenario** (Mw 7.2 Dauki, 300 Monte Carlo iterations, midday):

| Node type | Direct | Total (cascade) | Amplification |
|---|---|---|---|
| Power | 0.139 | 0.600 | 4.3× |
| Communication tower | 0.127 | 0.766 | 6.0× |
| Hospital (functional loss) | 0.085 | 0.604 | 7.1× |
| Bridge | 0.069 | 0.068 | 1.0× |

Population-weighted (Mw 7.2 Dauki): 67% power loss, 68% comm loss, 65%
bridge-access disruption; expected rescue-delay factor **1.90×**.

### Multi-scenario ensemble (novelty)

Six scenarios (4 Dauki train + 2 Madhupur test), 300 MC each — see
`config/scenarios.yaml` and `data/processed/cascade_ensemble_manifest.json`.

| Scenario | P(power lost) | P(comm lost) | Delay factor |
|---|---|---|---|
| Mw 6.8 Dauki | 0.47 | 0.47 | 1.65× |
| Mw 7.0 Dauki | 0.59 | 0.58 | 1.78× |
| **Mw 7.2 Dauki** | **0.67** | **0.68** | **1.90×** |
| Mw 7.5 Dauki | 0.83 | 0.85 | 2.09× |
| Mw 6.5 Madhupur | 0.98 | 0.99 | 2.31× |
| Mw 7.0 Madhupur | **1.00** | **1.00** | **2.34×** |

Headline: **proximity to the Madhupur fault dominates magnitude** — a Mw 7.0
Madhupur event produces near-total lifeline failure and higher delay than a
Mw 7.2 Dauki event, despite lower magnitude.

### Physics-informed surrogate emulator

| Model | Split | MAE | R² |
|---|---|---|---|
| **Production GraphSAGE** (Mw 7.2 Dauki) | 75/25 node hold-out | 0.016 | 0.993 |
| **Cross-scenario GraphSAGE** | Held-out Madhupur scenarios | **0.078** | **0.883** |
| Direct fragility baseline | Held-out Madhupur | 0.117 | 0.305 |

Cross-scenario generalization (R² = 0.883) confirms the surrogate learns
transferable cascade structure, not just one graph's noise.

Figures: F9.1–F9.4. Tables: T9.1–T9.3.

## 6. Earthquake Resilience Index (ERI)

Composite zone-level index (`config/resilience.yaml`), midday Mw 7.2 Dauki:

| Metric | Value |
|---|---|
| Citywide ERI | **70.9** (very-high tier) |
| Mean zone ERI | 69.4 |
| Zones: very high (≥70) | 252 |
| Zones: high (55–70) | 235 |

Components (0–1, higher = more resilient): structural 0.60, emergency capacity
0.86, lifeline robustness 0.61, accessibility 0.81. Lifeline and structural
components are the binding constraints; emergency-capacity headroom is higher
under the HAZUS casualty totals.

Output: `data/processed/dhaka_resilience_index.gpkg`.

Entropy--hybrid weighting (spatially varying components only) yields citywide
ERI **76.1** vs **70.9** under manual YAML weights (`outputs/eri_weight_comparison.json`).

## 8. Uncertainty propagation & external validation

### One-at-a-time sensitivity (`outputs/sensitivity_studies.json`)

| Test | Max change |
|---|---|
| GMPE 40/60–60/40 | ≤3.6% amplified PGA |
| Non-residential occupancy ±20% | 0.9% casualties |
| ERI weights ±0.10 | ≤1.7 points |
| Cascade probs ±0.15 | up to 11.8% delay |
| Vs30 ±20% | up to 8.6% mean collapse |
| MC count 50–500 | <1.2% delay range |

### Latin Hypercube UQ (`outputs/latin_hypercube_uq.json`, N=128)

| Metric | Mean | 95% CI |
|---|---|---|
| Mean collapse probability | 0.41 | 0.33–0.47 |
| Midday casualties (millions) | 0.32 | 0.19–0.41 |
| Cascade delay factor | 1.90 | 1.60–2.22 |
| Citywide ERI | 69.1 | 64.0–75.2 |

### External validation (`outputs/external_validation.json`)

- Reference Mw 7.2 Dauki at 158 km: bedrock PGA 0.160 g, amplified mean 0.224 g.
- 150 km envelope check: **pass** (0.169 g within CDMP-style 0.06–0.18 g).
- 1897 Assam analog (250 km, Mw 8.1): model MMI 8.3 vs macroseismic VI–VII
  (6.5–7.5) — **overpredicts**; qualitative shaking check only.

Architecture figure: `paper/figures/dt_architecture.pdf`.

## 9. Key limitations

- OSM construction/occupancy tags missing for ~95% of buildings.
- Network routing connects only **5.9%** of buildings to hospitals via the road
  graph; most assignments still use straight-line fallbacks.
- Open Buildings height merge optional; OSM `building:levels` defaults dominate.
- Eight communication towers mapped in OSM; cascade comm layer is indicative.
- Dependency wiring is proximity-based, not actual utility topology.
- Cross-scenario surrogate emulator R² (0.883) is lower than single-scenario GraphSAGE (0.993) — report
  both to show generalization vs overfitting trade-off.
- External validation limited to literature envelopes and 1897 analog; no ShakeMap,
  post-event damage survey, or observed hospital/utility outage data.

## 10. Data-quality fixes (consolidation baseline)

1. **Population plausibility caps** — max building population 5,333; citywide
   total 4.53 M (−2.8% vs uncapped).
2. **Population-conserving diurnal redistribution** — no phantom population loss
   at midday.
