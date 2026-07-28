"""
Feature Family 6: Recency-weighted form
Intra-season half/quarter split with second-half overweighting — proxy for jury recency bias per Key Focus §6

Implementation note: Intra-season splits not available from Wikipedia career stats (only full season aggregates).
Therefore using signature_moment_flag as proxy, since trophy finals occur late season (May-July) and capture recency bias.

Future work: if FBRef advanced metrics become available, could compute second-half form via match logs.
"""

# Proxy feature is signature_moment_flag already computed in narrative flagger
# This module documents the design choice
