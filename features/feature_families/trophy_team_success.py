"""
Feature Family 2: Trophy/team success
Categorical + continuous encodings for team achievements
- ucl_winner, league_winner, domestic_and_ucl_double
"""

def compute_trophy_features(club_raw, award_year, ucl_map, dom_map):
    """Compute trophy flags for a player-year"""
    ucl_winner = 0
    league_winner = 0
    ucl_name = ucl_map.get(award_year)
    if ucl_name and club_raw:
        if ucl_name.lower() in str(club_raw).lower() or str(club_raw).lower() in ucl_name.lower():
            ucl_winner = 1
    # domestic map: year -> list winners
    winners = dom_map.get(award_year, [])
    if club_raw and winners:
        for w in winners:
            if w.lower() in str(club_raw).lower() or str(club_raw).lower() in w.lower():
                league_winner = 1
                break
    double = 1 if (ucl_winner and league_winner) else 0
    return ucl_winner, league_winner, double
