# Reviewer #2 Response Plan — QuakeTwin Manuscript

**Current assessment:** 8.8/10 — strong systems paper; major revisions needed for Q1 targets (Earthquake Spectra, CEUS, Computers Environment and Urban Systems).

**Core reframe for revision:** Emphasize **integrated digital twin**, not an isolated GNN. The GCN is a physics-informed surrogate emulator that accelerates Monte Carlo cascade simulation; the novelty is end-to-end coupling under open-data constraints.

---

## Priority A — Must fix before Q1 resubmission

| Reviewer concern | Action | Status |
|------------------|--------|--------|
| Digital Twin vs GIS | Motivation paragraph | **Done** — `paper/main.tex` §1 |
| Narrow related work | Expanded Table 1 + OpenQuake, GEM, HAZUS, SimCenter, ShakeCast | **Done** |
| 95% unknown buildings | Epistemic caveat in Introduction | **Done** |
| GMPE weights | 40/60–60/40 sensitivity | **Done** — max 3.6% amplified PGA |
| Liquefaction | Equation + Iwasaki/Borcherdt | **Done** |
| Vs30 uncertainty | Raster range stated; ±20% class sensitivity | **Done** — up to 8.6% mean collapse change |
| Occupancy multipliers | HAZUS framing + non-residential ±20% | **Done** — 0.9% casualty change |
| Network routing 5.9% | Proof-of-concept framing | **Done** |
| Cascade probabilities | Ouyang cite + ±0.15 sensitivity | **Done** — up to 11.8% delay change |
| Why 300 MC? | Convergence 50–500 | **Done** — `outputs/mc_convergence.json` |
| Confidence intervals | MC std + 95% CI on delay | **Done** — CI 1.88–1.93 at N=300 |
| Why GCN architecture? | Surrogate emulator ablation | **Done** — GraphSAGE best (R²=0.992); Table `tab:gnn_ablation` |
| ERI weights | ±0.10 one-at-a-time | **Done** — max 1.7 points |
| Prior-study comparison | Discussion paragraph | **Done** |
| Sensitivity summary | §6 + table | **Done** |

---

## Priority B — Strengthen for 9.5+ impact

| Enhancement | Action | Status |
|-------------|--------|--------|
| Uncertainty quantification | Latin Hypercube over GMPE + fragility + cascade; CIs on citywide metrics | **Done** — `outputs/latin_hypercube_uq.json`, Table `tab:uq_ci` |
| Historical / regional validation | GSHAP/CDMP envelopes + 1897 Assam analog replay | **Done** — `outputs/external_validation.json`; honest overprediction noted |
| Digital twin architecture | Figure: data streams → twin state → surrogate emulator → dashboard | **Done** — `paper/figures/dt_architecture.pdf` |
| Figure quality | Vector PDF; larger fonts in publish style | **Partial** — DT figure + `PUBLICATION_RC` in `figures.py`; regenerate phase figures on demand |
| ERI weighting alternatives | Entropy / hybrid vs manual | **Done** — `outputs/eri_weight_comparison.json`; hybrid Δ5.2 pts |
| Real-time claim | Clarify surrogate vs full MC; Phase 6 feeds | **Done** — §architecture + limitations |

---

## Priority C — Data upgrades (when available)

- DGHS hospital bed census → replace OSM capacity proxy
- DPDC/DESCO feeder topology → replace proximity power graph
- BBS / mobile occupancy → replace diurnal multipliers
- Borehole SPT/CPT → calibrate liquefaction index

---

## Reviewer questions — draft answers

**Why GCN (not “why GNN”)?** The contribution is the digital twin; GCN is the implementation of the physics-informed surrogate emulator. Spectral convolution on normalized adjacency is the standard baseline for node-level regression on static graphs (Kipf & Welling 2017); we ablate against GraphSAGE, GAT, and MLP to justify the choice.

**Why these cascade probabilities?** Literature-informed conditional failure rates for interdependent infrastructure (Ouyang 2014); sensitivity analysis shows amplification factors stable within ±15% perturbation (to be reported).

**Why ERI weights?** Manual weights reflect stakeholder priors; entropy--hybrid weighting on spatially varying components shifts citywide ERI by 5.2 points (70.9 → 76.1); one-at-a-time ±0.10 perturbations change ERI by ≤1.7 points.

**Why 300 MC?** Convergence analysis shows citywide delay factor stabilizes within ±2% of the 500-iteration mean by N≥200 (see supplementary figure).

**Digital twin vs simulator?** QuakeTwin maintains a persistent building-resolved state graph, supports scenario injection and surrogate-backed interactive exploration, and is architected for live data replacement (seismic feeds, hospital status) — unlike a one-off GIS overlay or static HAZUS run.

**OpenQuake comparison?** OpenQuake provides regional hazard and loss engines; QuakeTwin adds building-resolved OSM stock, diurnal exposure, network routing, cascade simulation, and a physics-informed surrogate emulator at city scale with fully open Dhaka-specific outputs.

**Generalize beyond Dhaka?** Pipeline is config-driven; graph schema and YAML parameters transfer; data extraction scripts are city-specific.

---

## Suggested revision timeline

1. **Week 1:** Paper text (DT motivation, related work, uncertainty framing, proof-of-concept language)
2. **Week 2:** Run MC convergence, GNN ablation, ERI/GMPE sensitivity scripts; add CI columns to tables
3. **Week 3:** Architecture figure, discussion comparisons, supplementary material
4. **Week 4:** Figure polish, final proofread, Zenodo archive + GitHub URL

---

## Files to update when experiments complete

- `paper/main.tex` — sensitivity subsection, ablation table, CI in cascade table
- `docs/results_summary.md` — match new numbers
- `docs/methodology.md` — sensitivity protocols
- `outputs/supplementary/` — convergence plot, ablation CSV
