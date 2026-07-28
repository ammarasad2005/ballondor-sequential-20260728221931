"""
Feature Family 3: International Tournament Boost
Calendar-year flag + performance
- is_world_cup_year, is_euro_year, is_copa_year
- nation_won_world_cup, nation_won_euro, nation_won_copa, nation_won_any_international
"""

def compute_international_flags(nation, award_year, eval_type, wc_map, euros_map, copa_map):
    years_to_check = [award_year]
    if eval_type == "season":
        years_to_check.append(award_year-1)
    is_wc = 1 if award_year in wc_map else 0
    is_euro = 1 if award_year in euros_map else 0
    is_copa = 1 if award_year in copa_map else 0

    won_wc = won_euro = won_copa = 0
    for y in years_to_check:
        wc_winner = wc_map.get(y)
        if wc_winner and nation and (nation.lower() in wc_winner.lower() or wc_winner.lower() in nation.lower()):
            won_wc = 1
        euro_winner = euros_map.get(y)
        if euro_winner and nation and (nation.lower() in euro_winner.lower() or euro_winner.lower() in nation.lower()):
            won_euro = 1
        copa_winner = copa_map.get(y)
        if copa_winner and nation and (nation.lower() in copa_winner.lower() or copa_winner.lower() in nation.lower()):
            won_copa = 1
    won_any = 1 if (won_wc or won_euro or won_copa) else 0
    return is_wc, is_euro, is_copa, won_wc, won_euro, won_copa, won_any
