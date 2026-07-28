# Web Layer Handoff — Ballon d'Or Prediction Engine

Date: 2026-07-28
Status: Phase 8 Handoff (CLI pipeline validated, web layer out of scope for this build per Implementation Plan)

## Overview
The CLI/pipeline tool (Stages 0-6) is the primary deliverable. The web layer is a thin presentation layer over Stage 6's JSON output contract — no reimplementation of modeling logic in a second language/service (per Architecture §4.8).

This document describes the stable JSON contract and how to invoke inference as a service, so a future build session (agent or human) can pick up web implementation without re-deriving context.

## JSON Output Contract (Versioned Schema v0.1)

**File:** `inference/predict_season.py` produces JSON conforming to Architecture Blueprint §4.7

```json
{
  "season_id": "2024",
  "generated_at": "2026-07-28T15:16:28.343415+00:00",
  "model_version": "tier_b_linear_ranker_v1",
  "model_description": "Pairwise linear ranker trained on 63 seasons (1956-2025 excluding held-out), 11 features, L2 C=0.5",
  "feature_registry": "/home/user/features/feature_registry.yaml",
  "rankings": [
    {
      "rank": 1,
      "player": "Lautaro Martínez",
      "canonical_id": "lautaro-martinez-1997",
      "club": "Inter Milan",
      "nation": "Argentina",
      "position": "forward",
      "score": 2.507,
      "actual_rank": 7,
      "top_contributing_features": [
        {
          "feature": "nation_won_any_international",
          "contribution": 1.029,
          "scaled_value": 2.92,
          "raw_value": 1.0
        },
        {
          "feature": "goals_percentile_in_year",
          "contribution": 0.917,
          "scaled_value": 2.52,
          "raw_value": 87.9
        }
      ]
    }
  ]
}
```

### Field Definitions
- `season_id`: str, canonical year label used by France Football (e.g., "2024")
- `generated_at`: ISO8601 UTC timestamp
- `model_version`: str, e.g., "tier_b_linear_ranker_v1" — selected model per model_selection_report.md (Tier B pairwise linear ranker)
- `rankings`: list sorted by predicted rank ascending (rank 1 = predicted winner)
  - `rank`: int, predicted rank (1 = winner)
  - `player`: str, raw name as appears in ground_truth
  - `canonical_id`: str, slug + birth year (e.g., lionel-messi-1987) for entity resolution
  - `club`: str, primary club during eval period
  - `nation`: str, national team
  - `position`: str, grouped position (forward, midfielder, defender, goalkeeper, unknown)
  - `score`: float, linear model score = w·features (scaled), higher = better predicted rank
  - `actual_rank`: int | null, actual Ballon d'Or rank if season is historical (for evaluation), null if future undecided season
  - `top_contributing_features`: list of up to 5 dicts, sorted by absolute contribution descending
    - `feature`: str, feature name from registry (e.g., "goals_percentile_in_year", "ucl_winner")
    - `contribution`: float, coefficient * scaled_value — positive means boosted rank, negative penalized
    - `scaled_value`: float, feature value after StandardScaler transform (what model actually uses)
    - `raw_value`: float, raw feature value before scaling (human interpretable, e.g., 87.9 percentile)

### Stability Guarantee
- Contract version v0.1 is stable across independent runs for different seasons (tested 2024 and 2025 produce same schema)
- New fields may be added in future versions but existing fields will not be removed or renamed without version bump
- Model version string changes when model retrained (e.g., tier_b_v2)

## How to Invoke Inference as a Service Call

### CLI (Current Implementation)
```bash
python3 inference/predict_season.py --season 2024 --output reports/prediction_2024.json
python3 inference/predict_season.py --season 2025
python3 inference/predict_season.py --season 2026  # future, will fallback to most recent if not in features.parquet
```

### Python API (For Web Backend)
```python
from inference.predict_season import predict_season
output = predict_season("2024")  # season_id str
# output is dict conforming to contract above
# Save or return via API
```

### Dependencies
- `data/processed/features.parquet` must exist (built in Phase 4)
- `models/tier_b_model.pkl` and `tier_b_scaler.pkl` must exist (built in Phase 5)
- `data/processed/tier_b_features_used.json` lists feature cols and coefficients
- All paths relative to repo root, or use absolute paths

### Performance
- Inference for one season (30 players) takes <1 second, no GPU needed
- Model size <100KB (linear coefficients + scaler)

## Scenario Tool (What-If Interaction Model)

User's stated interest: "varying the values of the metrics, see rank shift live"

**Interaction Model for Web Layer:**

1. **Season Browser**: List all seasons 1956-2025, show actual vs predicted ranking, highlight discrepancies
2. **Per-Player Explanation Panel**: For selected player in predicted ranking, show:
   - Top contributing features (from `top_contributing_features`)
   - Bias notes (from `inference/explain.py` — e.g., "Predicted rank suppressed partly by positional base rate (defender) — historically only 5 defender winners")
   - Raw feature values vs peer percentile
3. **Scenario Tool ("What-If I change this player's metric")**:
   - Frontend: Sliders for adjustable features (e.g., league_goals, ucl_winner flag, club prestige)
   - Backend: On slider change, recompute player's feature vector, re-scale with same scaler, compute new score = w·features, re-rank within season's candidate pool (keep other players' scores fixed)
   - Return updated ranking and explanation delta: "Increasing goals from 10 to 30 (percentile 50->90) would boost score +0.8, moving from rank 7 to rank 2"
   - Implementation: Reuse `compute_contributions` from `predict_season.py` and `explain.py` — no new modeling logic in frontend
   - Must not re-train model, only re-score with existing weights

**Example Scenario:**
- User selects 2024 Rodri (actual winner rank 1, predicted 14)
- Sees explanation: boosted by club prestige (+0.75), nation Euro win (+0.64), but penalized missing stats (-0.49)
- User adjusts: set is_missing_stats=0 (pretend stats available) and increase goals_percentile from 52 to 80
- Backend re-scores: new score maybe 2.2, rank moves from 14 to 5 — still not winner due to attacker bias, illustrating model's limitations

## Web Layer Architecture (Thin Design per Blueprint §4.8)

```
Frontend (React/Vue/etc, not implemented now):
  - Season browser component: GET /api/seasons -> list
  - Ranking table: GET /api/predict?season=2024 -> JSON contract
  - Explanation panel: uses top_contributing_features from same JSON
  - Scenario sliders: POST /api/scenario {season_id, player, modified_features} -> re-ranked JSON

Backend (FastAPI/Flask thin wrapper):
  - No modeling logic reimplemented — directly calls predict_season(season_id) function
  - For scenario: loads features.parquet, applies user modifications to one player's feature row, re-computes scores via same model/scaler, returns updated JSON
  - Caches features.parquet in memory for speed

No new modeling logic should live in web layer — it is presentation layer over Stage 6 only, to avoid drift between CLI and web results (per Blueprint §4.8)
```

## Data Sources for Current Season (Future Work)

For live current season (e.g., 2025-26 season, award 2026):
- Candidate pool: Would need to scrape Ballon d'Or 30-man shortlist when announced (usually August/September) from France Football or Wikipedia
- Individual stats: Need to scrape current season stats for candidates (goals, etc) from Wikipedia or alternative source (FBRef blocked, but could attempt again with undetected_chromedriver)
- Trophy outcomes: UCL winner known by June, league winners by May, international tournaments by July — all scrapable via trophy_scraper.py (already handles 2025-26 season parsing correctly after bug fix)
- Then build features for new season using same build_features.py logic, but with candidate pool not in ground_truth

Current implementation handles historical seasons only; future season support requires extending stats scraper to handle new candidates not in canonical_players.parquet

## Known Limitations and Bias Transparency (P5)

- Attacker overrepresentation: forwards 50 winners vs defender 5, goalkeeper 1 — model includes position flags but still underpredicts defensive winners (e.g., Rodri 2024 predicted 14 vs actual 1)
- Big-club bias: club_prestige_score +0.298 positive — models bias, surfaced in explanation
- European competition bias: ucl_winner +0.270 positive
- Recency bias: signature_moment_flag originally negative due to multicollinearity, after fix +0.092 positive small — recency effect captured via trophy timing
- Missing stats: 27% overall, classical 31.5% vs modern 4.1% — flagged via is_missing_stats penalty
- Advanced metrics missing: xG, xA, progressive, SCA not available due to FBRef block — documented gap per Key Focus §9

## Files for Web Layer Implementation

- `inference/predict_season.py`: main inference entry point
- `inference/explain.py`: detailed per-candidate explanation with bias notes
- `data/processed/features.parquet`: feature matrix
- `models/tier_b_model.pkl`, `tier_b_scaler.pkl`: selected model
- `features/feature_registry.yaml`: feature definitions, era availability, bias notes
- `reports/prediction_*.json`: example outputs for 2024, 2025
- `reports/validation_report_2026-07-28.md`: validation metrics, per-era breakdown
- `reports/model_selection_report.md`: why Tier B selected

## Exit Criterion Check for Phase 8

- JSON output contract stable and versioned: YES (v0.1, tested across 2024 and 2025 independent runs, same schema)
- WEB_LAYER_HANDOFF.md exists: YES (this file)
- JSON contract demonstrably stable across at least two independent predict_season.py runs for different seasons: YES (2024 and 2025 both produce same fields)
- Phase 8 EXIT MET (handoff only, no web implementation beyond doc per user's CLI-first preference)

## Next Steps for Future Agent (Web Layer Phase 2)

- Build FastAPI backend wrapping predict_season.py
- Build frontend season browser + explanation panel + scenario tool
- Ensure no modeling logic drift — reuse same model artifacts
- Add current-season candidate scraping for live predictions
