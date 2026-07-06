# Paper — Elsevier CAS LaTeX source

`main.tex` is the complete Elsevier CAS single-column (`cas-sc`) manuscript for
**QuakeTwin Dhaka**, aligned with:

- `docs/results_summary.md` — headline numbers
- `docs/methodology.md` — thesis chapter mapping
- `outputs/phase*/figures/` — publication figures (copied to `paper/figures/`)

The manuscript covers Phases 1–5 plus quality upgrades: GMPE logic-tree, Vs30,
HAZUS casualties, network routing, six-scenario cascade ensemble,
physics-informed surrogate emulator (GraphSAGE; R² = 0.992 single / 0.883 cross-scenario), and Earthquake Resilience Index (ERI = 70.9).

## Compile

LaTeX is not installed on this machine. Easiest options:

1. **Overleaf (recommended)** — upload `main.tex`, `cas-refs.bib`, `cas-sc.cls`
   (from els-cas-templates), `model1-num-names.bst`, and `figures/`.
   Compiler: pdfLaTeX. Compile twice plus BibTeX.

2. **Local MiKTeX/TeX Live:**

   ```bash
   pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
   ```

## Before submission

- Verify CDMP (2009) and Islam et al. (2020) citation details
- Repository: https://github.com/subtlemyst/quaketwin-dhaka
- Regenerate figures: `python scripts/regenerate_publication_figures.py`
- If pipeline figures are regenerated, re-copy from `outputs/phase*/figures/`:

  ```powershell
  Copy-Item -Force outputs\phase*\figures\*.png paper\figures\
  ```

- Add ORCID via `\author[1]{...}[orcid=...]` if desired

## Key numbers to verify in abstract/results

| Claim | Value |
|-------|-------|
| Mean amplified PGA | 0.224 g |
| Mean collapse p | 0.40; 0.33% buildings ≥ 0.5 |
| Midday HAZUS casualties | 322,837 |
| Hospital overload | 243 / 728 |
| Cascade delay factor (Mw 7.2 Dauki) | 1.90× |
| Cross-scenario surrogate emulator R² | 0.883 |
| Single-scenario GraphSAGE R² | 0.992 |
| Citywide ERI | 70.9 |

Full tables: `docs/results_summary.md`.
