# Model Selection Report — Tier D (Phase 5 Task 4)

Date: 2026-07-28 15:04:25.044914

## Decision

**Selected Model: tier_b_linear_ranker** — Pairwise Linear Ranker (Tier B)

### Reasoning

1. Tier A baseline: Top-1 LOSO 27.0%, Expanding 26.5%, Held-out 0%, Spearman LOSO 0.322 — floor reference

2. Tier B linear: Top-1 LOSO 25.4% slightly lower than A, but Top-3 49.2% vs 44.4%, Top-5 68.3% vs 55.6%, Spearman 0.361 vs 0.322 — better full ranking

3. Tier B Expanding: Top-1 20.4% vs A 26.5% but Top-5 71.4% vs 57.1% and Spearman 0.340 vs 0.301 — consistent improvement in rank correlation

4. Tier B Held-out: Spearman 0.409 vs A 0.316 and C 0.378 — best rank correlation on unseen recent seasons

5. Tier C GBM: Train Top-1 23.8% < B, Held-out Top-1 16.7% (1/6) is one lucky obvious winner (2022 Benzema) but Spearman worse than B (0.378 vs 0.409) and early stopping at iteration 0 indicates overfitting

6. Per Architecture Blueprint P3: Prefer simple interpretable until complexity earns its place. Tier C does not earn its complexity — no consistent non-marginal improvement across multiple validation folds

7. Per decision rule §4.5: Prefer B unless C shows consistent improvement — C fails this, so select B

## Metrics Comparison

### LOSO CV (63 training seasons, held-out excluded)

| Tier | Top1 | Top3 | Top5 | Spearman | Kendall |
|------|------|------|------|----------|---------|
| A | 27.0% | 44.4% | 55.6% | 0.322 | 0.234 |
| B | 25.4% | 49.2% | 68.3% | 0.361 | 0.265 |
| C | 23.8% | - | - | - | - | (train only)

### Expanding Window (49 seasons evaluated from 1970+)

| Tier | Top1 | Top3 | Top5 | Spearman |
|------|------|------|------|----------|
| A | 26.5% | 42.9% | 57.1% | 0.301 |
| B | 20.4% | 44.9% | 71.4% | 0.34 |

### Held-Out Final (6 seasons: 2018,2019,2021-2024) — One-Shot

| Tier | Top1 | Top3 | Top5 | Spearman |
|------|------|------|------|----------|
| A | 0.0% | 16.7% | 33.3% | 0.316 |
| B | 0.0% | 16.7% | 50.0% | 0.409 |
| C | 16.7% | 16.7% | 50.0% | 0.378 |

## Feature Importance (Tier B Coefficients)

| Feature | Coefficient (scaled) | Interpretation |
|---------|----------------------|----------------|
| goals_percentile_in_year | 0.363 | positive predictive |
| nation_won_any_international | 0.352 | positive predictive |
| is_missing_stats | -0.3 | negative |
| club_prestige_score | 0.298 | positive predictive |
| ucl_winner | 0.266 | positive predictive |
| signature_moment_flag | -0.153 | negative |
| is_goalkeeper | 0.116 | positive predictive |
| league_winner | 0.098 | positive predictive |
| is_forward | 0.035 | positive predictive |
| is_defender | -0.009 | negative |

## Bias Handling (P5)

- **attacker_overrepresentation**: Modeled via is_forward positive small bonus, is_defender negative, goalkeeper positive? Actually is_goalkeeper 0.116 positive small but only one winner Yashin — coefficient small, not major. Position group distribution shows forward 50 winners vs defender 5, goalkeeper 1 — model captures this via position features, and explanation layer can surface when rank suppressed by positional base rate per P5

- **big_club_bias**: club_prestige_score +0.298 positive — models big-club/media-market bias explicitly, surfaced in explanation

- **european_competition_bias**: ucl_winner +0.266 positive — Champions League performance heavily weighted

- **recency_bias**: signature_moment_flag intended as recency proxy but coefficient -0.153 negative due to overlap with ucl/nation flags — suggests recency effect captured via trophy timing already, and separate flag not additive. This is an honest finding worth reporting per Key Focus §6 (validate empirically, if doesn't improve metrics, report as finding)

- **tournament_boost**: nation_won_any +0.352 positive — international tournament win boost strong

## Conclusion

Tier B selected as primary per interpretability and consistent rank correlation improvement. Tier A remains floor. Tier C not selected due to overfitting and lack of consistent improvement. No model achieves high top-1 accuracy on held-out recent controversial years (0% for A/B, 16.7% for C) — honestly reported per Phase 6 Task 4, not cue to tune further.
