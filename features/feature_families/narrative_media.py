"""
Feature Family 7: Narrative/media signal
Best-effort, partially manual-flagged
- club_prestige_tier, club_prestige_score, market_size_proxy, signature_moment_flag

Per Requirements A.4: any agent-inferred flag must be logged as such — see data/raw/narrative/inference_log.md

Per Key Focus Area §3: avoid leakage from post-hoc narrative descriptions and betting odds.

Operationalization:
- club_prestige_tier: Tier1 = high revenue/UEFA coefficient clubs (Real Madrid, Barcelona, Bayern, ManU, etc)
- market_size_proxy = prestige_score 1-3
- signature_moment_flag = 1 if club won UCL or nation won major international in relevant period
"""
