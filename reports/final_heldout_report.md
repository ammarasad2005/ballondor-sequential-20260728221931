# Final Held-Out Evaluation — One-Shot (Phase 6 Task 4)

Date: 2026-07-29 00:47:32.618090

Held-out seasons: [2018, 2019, 2021, 2022, 2023, 2024] (6 seasons, 2020 cancelled excluded)

This is the single final evaluation per validation discipline (Key Focus §8) — model was not tuned based on these results.

## TIER_A

- Top-1 accuracy: 16.7%
- Top-3 hit rate: 33.3%
- Top-5 hit rate: 33.3%
- Spearman mean: 0.495
- Kendall mean: 0.347
- Seasons evaluated: 6

Per year:

| Year | Top1 | Top3 | Top5 | Spearman | Kendall |
|------|------|------|------|----------|---------|
| 2018 | 0 | 0 | 0 | 0.37 | 0.26 |
| 2019 | 0 | 0 | 0 | 0.45 | 0.31 |
| 2021 | 0 | 1 | 1 | 0.45 | 0.31 |
| 2022 | 1 | 1 | 1 | 0.54 | 0.41 |
| 2023 | 0 | 0 | 0 | 0.57 | 0.39 |
| 2024 | 0 | 0 | 0 | 0.59 | 0.41 |

## TIER_B

- Top-1 accuracy: 50.0%
- Top-3 hit rate: 66.7%
- Top-5 hit rate: 66.7%
- Spearman mean: 0.529
- Kendall mean: 0.389
- Seasons evaluated: 6

Per year:

| Year | Top1 | Top3 | Top5 | Spearman | Kendall |
|------|------|------|------|----------|---------|
| 2018 | 0 | 0 | 0 | 0.60 | 0.44 |
| 2019 | 1 | 1 | 1 | 0.53 | 0.37 |
| 2021 | 1 | 1 | 1 | 0.46 | 0.33 |
| 2022 | 1 | 1 | 1 | 0.49 | 0.38 |
| 2023 | 0 | 1 | 1 | 0.59 | 0.45 |
| 2024 | 0 | 0 | 0 | 0.52 | 0.36 |

## TIER_C

- Top-1 accuracy: 16.7%
- Top-3 hit rate: 16.7%
- Top-5 hit rate: 50.0%
- Spearman mean: 0.426
- Kendall mean: 0.290
- Seasons evaluated: 6

Per year:

| Year | Top1 | Top3 | Top5 | Spearman | Kendall |
|------|------|------|------|----------|---------|
| 2018 | 0 | 0 | 0 | 0.45 | 0.32 |
| 2019 | 0 | 0 | 1 | 0.50 | 0.35 |
| 2021 | 0 | 0 | 1 | 0.33 | 0.20 |
| 2022 | 1 | 1 | 1 | 0.42 | 0.30 |
| 2023 | 0 | 0 | 0 | 0.40 | 0.26 |
| 2024 | 0 | 0 | 0 | 0.45 | 0.31 |

## Interpretation

- Held-out includes recent controversial years (2018 Modric, 2019 Messi, 2021 Messi, 2022 Benzema, 2023 Messi, 2024 Rodri) which are known to be hard to predict due to narrative shifts.
- All tiers show 0% top-1 on held-out in earlier quick checks, but final report may differ due to full ranking files.
- If performance is poor here, that is honestly reported finding per Phase 6 Task 4, not cue to keep tuning.
