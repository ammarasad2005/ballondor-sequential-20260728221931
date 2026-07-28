"""
Feature Family 5: Peer-relative standing
Percentile within that year's candidate pool — critical for cross-era comparability per Key Focus §7
- goals_percentile_in_year, apps_percentile_in_year, goals_per_app_percentile_in_year
"""

def compute_percentile(series):
    return series.rank(pct=True, method='average')*100
