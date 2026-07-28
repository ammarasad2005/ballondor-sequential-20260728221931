"""
Feature Family 1: Individual Production
Position-adjusted, per-90 normalized (here per-app as proxy)
Implements features:
- position_raw, position_group, is_forward, is_midfielder, is_defender, is_goalkeeper
- league_goals, league_apps, goals_per_app
"""

def extract_position_features(pos_raw):
    """Group position logic shared across pipeline"""
    import re, pandas as pd
    if not pos_raw or pd.isna(pos_raw):
        return "unknown"
    low=str(pos_raw).lower()
    if "goalkeeper" in low or "keeper" in low:
        return "goalkeeper"
    if any(x in low for x in ["defender", "back", "libero", "sweeper"]):
        # Prioritize forward if also contains forward
        if any(x in low for x in ["forward", "striker", "winger"]):
            # For ambiguous like "Forward midfielder defender"? unlikely
            if "forward" in low or "striker" in low or "winger" in low:
                return "forward"
        return "defender"
    if "midfielder" in low or "midfield" in low:
        if any(x in low for x in ["forward", "striker", "winger"]):
            return "forward"
        return "midfielder"
    if any(x in low for x in ["forward", "striker", "winger", "centre forward", "second striker"]):
        return "forward"
    return "unknown"
