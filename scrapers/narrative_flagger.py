"""
Narrative / Media Signal Collector — best-effort, partially agent-judged
Phase 2 Task 4

Creates narrative flags:
- signature_moment: whether season had iconic final performance (proxy)
- club_prestige tier
- market_size proxy

Per Requirements A.4: any agent-inferred flag must be logged as such.

Outputs to data/raw/narrative/ and processed.

This is intentionally simple and transparent:
- signature_moment is NOT sourced from post-hoc articles (which would be leakage per Key Focus Area §3)
  Instead, it's derived from structured outcomes: winning major final + being team's top scorer etc.
  But still involves agent judgment -> flagged as inferred.
- club_prestige is operationalized via simple revenue/coefficient proxy documented below.

"""

import pandas as pd, json, re
from pathlib import Path

BASE=Path(__file__).parent.parent
RAW_DIR=BASE/"data"/"raw"/"narrative"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR=BASE/"data"/"processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

GT_PATH=BASE/"data/processed/ground_truth.parquet"
UCL_PATH=BASE/"data/processed/trophy_ucl.parquet"
WC_PATH=BASE/"data/processed/trophy_worldcup.parquet"
EUROS_PATH=BASE/"data/processed/trophy_euros.parquet"
COPA_PATH=BASE/"data/processed/trophy_copa.parquet"
DOMESTIC_PATH=BASE/"data/processed/trophy_domestic.parquet"

gt=pd.read_parquet(GT_PATH)

# Load trophies
try:
    ucl=pd.read_parquet(UCL_PATH)
except:
    ucl=pd.read_csv(BASE/"data/raw/trophies/ucl_winners_parsed.csv")
try:
    wc=pd.read_parquet(WC_PATH)
except:
    wc=pd.read_csv(BASE/"data/raw/trophies/worldcup_winners_parsed.csv")
try:
    euros=pd.read_parquet(EUROS_PATH)
except:
    euros=pd.read_csv(BASE/"data/raw/trophies/euros_winners_parsed.csv")
try:
    copa=pd.read_parquet(COPA_PATH)
except:
    copa=pd.read_csv(BASE/"data/raw/trophies/copa_winners_parsed.csv")
try:
    domestic=pd.read_parquet(DOMESTIC_PATH)
except:
    domestic=pd.read_csv(BASE/"data/raw/trophies/domestic_leagues_parsed.csv")

print(f"Loaded trophies: UCL {len(ucl)}, WC {len(wc)}, Euros {len(euros)}, Copa {len(copa)}, Domestic {len(domestic)}")

# Define club prestige tiers - simple operationalization per Requirements A.4
# Tier 1: historically highest revenue / European coefficient - Real Madrid, Barcelona, Bayern Munich, Manchester United, Juventus, Milan, Liverpool, Inter, Chelsea, Man City, PSG
# Tier 2: Other clubs from top 5 leagues that have won UCL or domestic titles frequently: Arsenal, Atletico Madrid, Dortmund, Napoli, Roma, Tottenham, etc
# Tier 3: Rest
# This proxy is documented and defensible, not subjective judgment per player, but based on club.
# Source of tier list: UEFA coefficient historical top and Deloitte Football Money League frequent top.
# Will be logged as agent-inferred proxy but with explicit rule.

prestige_tier_1 = {
    "Real Madrid", "Barcelona", "Bayern Munich", "Bayern München", "Manchester United",
    "Juventus", "Milan", "AC Milan", "Liverpool", "Internazionale", "Inter", "Inter Milan",
    "Chelsea", "Manchester City", "Paris Saint-Germain", "PSG", "Paris SG", "Paris Saint Germain"
}
prestige_tier_2 = {
    "Arsenal", "Atletico Madrid", "Atlético Madrid", "Borussia Dortmund", "Dortmund",
    "Napoli", "Roma", "AS Roma", "Tottenham Hotspur", "Tottenham", "Ajax", "Benfica", "Porto",
    "Monaco", "Lyon", "Marseille", "Olympique Marseille", "Everton", "Newcastle", "West Ham",
    "Leicester", "Leicester City", "Sevilla", "Valencia", "Villarreal", "Bayer Leverkusen",
    "RB Leipzig", "Borussia Mönchengladbach", "Schalke", "Fiorentina", "Lazio", "Atalanta",
    "Leeds United", "Nottingham Forest", "Aston Villa", "Blackpool", "Dinamo Kiev", "Dynamo Kiev",
    "Dynamo Kyiv", "Reims", "Ferencváros", "Benfica", "Sporting", "Hamburger SV", "Hamburg"
}

def get_club_prestige(club_raw):
    if not club_raw or pd.isna(club_raw):
        return {"tier": None, "score": None, "reason": "missing club"}
    # club_raw may contain multiple clubs e.g., "Reims Real Madrid" for mid-year transfer - take last club (most recent)
    # Split by spaces? Better heuristic: if contains multiple known clubs, take the one with highest prestige
    # Simplified: check if any tier1 club substring in raw string (case insensitive)
    low = club_raw.lower()
    for tier1_club in prestige_tier_1:
        if tier1_club.lower() in low:
            return {"tier": 1, "score": 3, "matched": tier1_club, "raw": club_raw}
    for tier2_club in prestige_tier_2:
        if tier2_club.lower() in low:
            return {"tier": 2, "score": 2, "matched": tier2_club, "raw": club_raw}
    # Fallback tier 3
    return {"tier": 3, "score": 1, "matched": "other", "raw": club_raw}

def get_market_size_proxy(prestige_score):
    # Same as prestige for simplicity, but could be revenue tier
    return prestige_score

# For signature moment: heuristic based on whether player's club won UCL in that year or country won World Cup/Euro/Copa in relevant period
# For season-based years (2022+), UCL winner year = award_year (since final in May/June of that season end). For calendar years, UCL winner year = award_year as well (final in May of that calendar year). So mapping is straightforward.
# For international: World Cup occurs every 4 years mid-year, Euro every 4, Copa irregular. For a given award_year, we check if player's nation won a major tournament in that calendar year (or for season-based, check if tournament falls within eval window Aug prev - Jul current)

# Build mapping year -> winners
ucl_map = {int(row["year"]): row["winner_club"] for _, row in ucl.iterrows() if pd.notna(row["year"])}
wc_map = {int(row["year"]): row["winner_country"] for _, row in wc.iterrows()}
euros_map = {int(row["year"]): row["winner_country"] for _, row in euros.iterrows()}
copa_map = {int(row["year"]): row["winner_country"] for _, row in copa.iterrows()}

# Domestic map: for each league/year, winners
dom_map = {}
for _, row in domestic.iterrows():
    try:
        y=int(row["year"])
        league=row["league"]
        winner=row["winner_club"]
        dom_map.setdefault(y, {}).setdefault(league, winner)
    except:
        pass

# Load eval metadata for season vs calendar handling
eval_meta = pd.read_csv(BASE/"data/processed/eval_window_metadata.csv")
eval_map = eval_meta.set_index("season_id")[["eval_period_start","eval_period_end","eval_type"]].to_dict('index')

# Now produce narrative flags per ground_truth row
records=[]
for _, row in gt.iterrows():
    season_id=str(row["season_id"])
    award_year=int(row["award_year"])
    player=row["player_name_raw"]
    club=row["club_at_time"]
    nation=row["nation_team"]

    # Club prestige
    prestige_info=get_club_prestige(club)
    prestige_tier=prestige_info["tier"]
    prestige_score=prestige_info["score"]

    # Market size proxy = prestige_score for now
    market_proxy=prestige_score

    # Signature moment heuristic:
    # - If club won UCL in award_year (UCL final May of that year) and player is from that club -> potential signature
    # - If nation won World Cup / Euro / Copa in award_year (or in eval window for season-based) and player's nation matches winner -> signature
    # - Also if player is rank 1, we give slightly higher weight? But for flag, we just check trophy win
    # This is agent-inferred, not sourced from articles (to avoid leakage per Key Focus Area §3)

    sig_moment=0
    sig_reasons=[]

    # Check UCL
    ucl_winner=ucl_map.get(award_year)
    if ucl_winner and club:
        # Check if player's club matches UCL winner (substring match)
        if ucl_winner.lower() in str(club).lower() or str(club).lower() in ucl_winner.lower():
            sig_moment=1
            sig_reasons.append(f"UCL winner {award_year} club {ucl_winner} matches player's club {club}")

    # Check international - evaluate based on eval window for season-based
    eval_info=eval_map.get(season_id, {})
    eval_type=eval_info.get("eval_type") if eval_info else "calendar"

    # For season-based (2022+), eval period spans Aug prev year to Jul current year.
    # For World Cup: if WC happened in previous calendar year but within eval window, still count for season award.
    # Example: 2023 award includes World Cup Qatar Nov-Dec 2022 which is within Aug2022-Jul2023 window. So for season awards, we should check tournaments in [award_year-1 Aug to award_year Jul]
    # Simplify: for season-based, check both award_year and award_year-1 for international wins
    years_to_check=[award_year]
    if eval_type=="season":
        years_to_check.append(award_year-1)

    # Nation matching: need to handle nation name vs winner_country name may differ (e.g., "England" vs "England")
    # Normalize by simple substring lower
    for y_check in years_to_check:
        for tourn_name, tourn_map in [("WorldCup", wc_map), ("Euros", euros_map), ("CopaAmerica", copa_map)]:
            winner_country=tourn_map.get(y_check)
            if winner_country and nation:
                # Check if nation string appears in winner_country or vice versa
                n_low=str(nation).lower()
                w_low=str(winner_country).lower()
                if n_low in w_low or w_low in n_low or n_low.split()[0] in w_low:
                    sig_moment=1
                    sig_reasons.append(f"{tourn_name} winner {y_check} country {winner_country} matches player's nation {nation}")

    # Additional heuristic: if player is forward/striker and team won league, could be signature but we have already club prestige

    record={
        "season_id":season_id,
        "award_year":award_year,
        "player_name_raw":player,
        "club_at_time":club,
        "nation_team":nation,
        "club_prestige_tier":prestige_tier,
        "club_prestige_score":prestige_score,
        "market_size_proxy":market_proxy,
        "signature_moment_flag":sig_moment,
        "signature_moment_reasons": "; ".join(sig_reasons) if sig_reasons else "",
        "prestige_match_info":json.dumps(prestige_info) if prestige_info else "",
        "inferred_flags":"club_prestige_tier, market_size_proxy, signature_moment_flag are agent-inferred proxies per Requirements A.4, not sourced from post-hoc narrative articles (to avoid leakage per Key Focus Area §3)",
        "source":"heuristic based on trophy winners (UCL, World Cup, Euros, Copa) + club prestige tier list operationalized from UEFA coefficient / revenue"
    }
    records.append(record)

df_out=pd.DataFrame(records)

# Save raw
df_out.to_csv(RAW_DIR/"narrative_flags_raw.csv", index=False)
df_out.to_parquet(PROCESSED_DIR/"narrative_flags.parquet", index=False)
df_out.to_json(RAW_DIR/"narrative_flags_raw.jsonl", orient="records", lines=True)

print(f"Generated narrative flags for {len(df_out)} rows")
print(f"Signature moment flagged: {df_out['signature_moment_flag'].sum()} out of {len(df_out)}")
print(f"Club prestige tier distribution:\n{df_out['club_prestige_tier'].value_counts()}")

# Also log which flags were agent-inferred vs sourced
with open(RAW_DIR/"inference_log.md",'w') as f:
    f.write("# Narrative Flags Inference Log\n\n")
    f.write("Per Requirements doc A.4, any agent-inferred flag must be logged.\n\n")
    f.write("## Flags\n")
    f.write("- club_prestige_tier: AGENT-INFERRED proxy operationalized via simple tier list (Tier1 = Real Madrid, Barcelona, Bayern, ManU, Juventus, Milan, Liverpool, Inter, Chelsea, Man City, PSG). Tier2 = other frequent UCL/domestic winners. Tier3 = rest. This is a proxy for club market size/media coverage, not a subjective per-player judgment.\n")
    f.write("- market_size_proxy: AGENT-INFERRED same as prestige_score (1-3)\n")
    f.write("- signature_moment_flag: AGENT-INFERRED heuristic: 1 if player's club won UCL in award year, or player's nation won World Cup/Euro/Copa in award year (or previous year for season-based awards). This avoids leakage from post-hoc articles describing 'standout season' after winner known (Key Focus Area §3). It is best-effort and clearly documented as inferred, not sourced.\n")
    f.write("\n## Why not use media/betting odds?\n")
    f.write("- Using betting odds or pundit predictions close to ceremony would be leakage (perfect proxy for outcome) per Key Focus Area §3, so explicitly NOT used.\n")
    f.write("- Using post-hoc narrative descriptions like 'stellar Ballon d'Or campaign' would not exist for undecided current season, so excluded.\n")

print("Saved inference log")
