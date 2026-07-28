# Narrative Flags Inference Log

Per Requirements doc A.4, any agent-inferred flag must be logged.

## Flags
- club_prestige_tier: AGENT-INFERRED proxy operationalized via simple tier list (Tier1 = Real Madrid, Barcelona, Bayern, ManU, Juventus, Milan, Liverpool, Inter, Chelsea, Man City, PSG). Tier2 = other frequent UCL/domestic winners. Tier3 = rest. This is a proxy for club market size/media coverage, not a subjective per-player judgment.
- market_size_proxy: AGENT-INFERRED same as prestige_score (1-3)
- signature_moment_flag: AGENT-INFERRED heuristic: 1 if player's club won UCL in award year, or player's nation won World Cup/Euro/Copa in award year (or previous year for season-based awards). This avoids leakage from post-hoc articles describing 'standout season' after winner known (Key Focus Area §3). It is best-effort and clearly documented as inferred, not sourced.

## Why not use media/betting odds?
- Using betting odds or pundit predictions close to ceremony would be leakage (perfect proxy for outcome) per Key Focus Area §3, so explicitly NOT used.
- Using post-hoc narrative descriptions like 'stellar Ballon d'Or campaign' would not exist for undecided current season, so excluded.
