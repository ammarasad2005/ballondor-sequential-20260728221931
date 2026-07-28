# Ballon d'Or Prediction Engine

A learning-to-rank system that models the Ballon d'Or jury's historical decision-making (1956–present) and generalizes to rank current-season candidates.

## Project Structure
See `01_ARCHITECTURE_BLUEPRINT.md` in uploads for full design, but repo follows:

```
data/raw/          # checkpointed scraper outputs
data/interim/      # post entity-resolution
data/processed/    # ground_truth.parquet, features.parquet
scrapers/
entity_resolution/
features/
models/
validation/
inference/
reports/
configs/run_config.yaml
```

## Operating Principles
- Rank, don't regress (P1)
- Generalize, don't memorize (P2) — validation discipline is load-bearing
- Interpretability first (P3)
- Two eras, one philosophy, different rigor (P4)
- Explicit bias handling (P5)

## Current Phase
Phase 0 — Environment & Scope Setup (see 02_IMPLEMENTATION_PLAN.md)

## Log
See PROJECT_LOG.md for detailed progress.

## Data Sourcing
Full autonomy per Requirements A.5 — no seed files provided. Scrapers verify ToS/robots and prefer structured tables.

## Model Tiers
- Tier A: explicit weighted-sum baseline
- Tier B: pairwise linear ranker (primary target)
- Tier C: gradient-boosted ranker (only if demonstrably better)
- Tier D: selection / light ensembling
