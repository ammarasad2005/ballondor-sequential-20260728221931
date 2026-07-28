"""
Build live features for 2025-26 season (2026 Ballon d'Or) using real shortlist from givemesport

Shortlist 20 contenders from https://www.givemesport.com/ballon-dor-power-rankings/ as of July 20 2026
"""

import pandas as pd, json, re
from pathlib import Path

BASE=Path(__file__).parent.parent

# Shortlist from givemesport ranking (July 20 2026)
shortlist=[
    {"rank_givemesport":1, "player":"Lamine Yamal", "club":"Barcelona", "nation":"Spain", "position":"Forward"},
    {"rank_givemesport":2, "player":"Harry Kane", "club":"Bayern Munich", "nation":"England", "position":"Forward"},
    {"rank_givemesport":3, "player":"Lionel Messi", "club":"Inter Miami", "nation":"Argentina", "position":"Forward"},
    {"rank_givemesport":4, "player":"Rodri", "club":"Manchester City", "nation":"Spain", "position":"Midfielder"},
    {"rank_givemesport":5, "player":"Ousmane Dembélé", "club":"Paris Saint-Germain", "nation":"France", "position":"Forward"},
    {"rank_givemesport":6, "player":"Kylian Mbappé", "club":"Real Madrid", "nation":"France", "position":"Forward",
     "stats_note":"44 games (8 World Cup), 42 goals (10 WC), 7 assists (4 WC) per givemesport"},
    {"rank_givemesport":7, "player":"Michael Olise", "club":"Bayern Munich", "nation":"France", "position":"Forward"},
    {"rank_givemesport":8, "player":"Jude Bellingham", "club":"Real Madrid", "nation":"England", "position":"Midfielder"},
    {"rank_givemesport":9, "player":"Declan Rice", "club":"Arsenal", "nation":"England", "position":"Midfielder"},
    {"rank_givemesport":10, "player":"Erling Haaland", "club":"Manchester City", "nation":"Norway", "position":"Forward"},
    {"rank_givemesport":11, "player":"Fabian Ruiz", "club":"Paris Saint-Germain", "nation":"Spain", "position":"Midfielder"},
    {"rank_givemesport":12, "player":"Pau Cubarsi", "club":"Barcelona", "nation":"Spain", "position":"Defender", "full_name":"Pau Cubarsí"},
    {"rank_givemesport":13, "player":"Pedri", "club":"Barcelona", "nation":"Spain", "position":"Midfielder"},
    {"rank_givemesport":14, "player":"Khvicha Kvaratskhelia", "club":"Paris Saint-Germain", "nation":"Georgia", "position":"Forward"},
    {"rank_givemesport":15, "player":"Desire Doue", "club":"Paris Saint-Germain", "nation":"France", "position":"Forward", "full_name":"Désiré Doué"},
    {"rank_givemesport":16, "player":"Vinicius Jr", "club":"Real Madrid", "nation":"Brazil", "position":"Forward", "full_name":"Vinícius Júnior"},
    {"rank_givemesport":17, "player":"Vitinha", "club":"Paris Saint-Germain", "nation":"Portugal", "position":"Midfielder"},
    {"rank_givemesport":18, "player":"Martin Odegaard", "club":"Arsenal", "nation":"Norway", "position":"Midfielder", "full_name":"Martin Ødegaard"},
    {"rank_givemesport":19, "player":"Unai Simon", "club":"Athletic Club", "nation":"Spain", "position":"Goalkeeper", "full_name":"Unai Simón"},
    {"rank_givemesport":20, "player":"Achraf Hakimi", "club":"Paris Saint-Germain", "nation":"Morocco", "position":"Defender"},
]

# Load existing features and trophy maps to reuse logic
import pandas as pd

# Load trophy winners (updated after fix)
ucl=pd.read_parquet(BASE/"data/processed/trophy_ucl.parquet")
wc=pd.read_parquet(BASE/"data/processed/trophy_worldcup.parquet")

# For 2026, UCL winner per our fixed parsing: season 2025-26 year 2026 winner PSG
# Check
print("UCL winners recent:")
print(ucl[ucl["year"]>=2023][["season","year","winner_club"]].to_string())

# World Cup 2026 winner Spain per web search (Spain beat Argentina 1-0)
# We need to add to wc map manually if not present (our wc scraping only up to 2022 maybe? Actually we have 23 winners, but 2026 not yet in Wikipedia trophy list? Let's check)
print("\nWC winners recent:")
print(wc.tail(10).to_string())

# For live prediction, we will manually set:
# UCL 2025-26 winner = Paris Saint-Germain (from UCL list year 2026)
# World Cup 2026 winner = Spain

# Load stats cache for 2025-26 season
import glob, json
stats_cache={}
for file in (BASE/"data/raw/stats_combined").glob("*.json"):
    try:
        with open(file) as f:
            data=json.load(f)
        raw=data.get("player_name_raw")
        if raw:
            stats_cache[raw]=data
    except:
        pass

def parse_season_end_year(season_str):
    import re
    if not season_str:
        return None
    s=str(season_str).strip()
    s=re.sub(r'\[.*?\]','',s)
    s=s.replace('–','-').replace('—','-')
    import re as re2
    years_4=re2.findall(r'\b(\d{4})\b', s)
    if len(years_4)>=2:
        return int(years_4[-1])
    if len(years_4)==1:
        m=re2.search(r'(\d{4})[-/]\s*(\d{2})\b', s)
        if m:
            first=int(m.group(1))
            two=int(m.group(2))
            century=first//100
            second=century*100+two
            if second<first:
                second+=100
            return second
        return int(years_4[0])
    m2=re2.search(r'(\d{4})[-/]\s*(\d{2})\b', s)
    if m2:
        first=int(m2.group(1))
        two=int(m2.group(2))
        century=first//100
        second=century*100+two
        if second<first:
            second+=100
        return second
    m3=re2.search(r'(\d{4})', s)
    if m3:
        return int(m3.group(1))
    return None

def find_stats_for_year(career_stats, award_year):
    if not career_stats:
        return None, None, []
    plausible=[]
    for entry in career_stats:
        season=str(entry.get("season","")).lower()
        if "total" in season or "career" in season:
            continue
        if len(season)>30:
            continue
        club=entry.get("club")
        if not club or str(club).strip().lower() in ["none",""]:
            continue
        g=entry.get("league_goals")
        a=entry.get("league_apps")
        if g is not None:
            try:
                if int(g)>60:
                    continue
            except:
                pass
        if a is not None:
            try:
                if int(a)>60:
                    continue
            except:
                pass
        plausible.append(entry)
    matches=[]
    for entry in plausible:
        end_year=parse_season_end_year(entry.get("season"))
        if end_year==award_year:
            matches.append(entry)
    if not matches:
        for entry in plausible:
            end_year=parse_season_end_year(entry.get("season"))
            if end_year==award_year+1:
                s=str(entry.get("season",""))
                import re
                years=re.findall(r'\b(\d{4})\b', s)
                start_year=None
                if years:
                    start_year=int(years[0])
                if start_year==award_year:
                    matches.append(entry)
    if not matches:
        return None, None, []
    total_g=0
    total_a=0
    has_g=False
    has_a=False
    for m in matches:
        g=m.get("league_goals")
        a=m.get("league_apps")
        if g is not None:
            try:
                total_g+=int(g)
                has_g=True
            except:
                pass
        if a is not None:
            try:
                total_a+=int(a)
                has_a=True
            except:
                pass
    return (total_g if has_g else None), (total_a if has_a else None), matches

# Build features for 2026 shortlist
records=[]
for entry in shortlist:
    player_raw=entry["player"]
    # Try to find exact match in stats_cache (need to handle accent variations)
    # Search for player name in cache keys via substring
    matched_key=None
    # First try exact
    if player_raw in stats_cache:
        matched_key=player_raw
    else:
        # Try case-insensitive contains
        for k in stats_cache.keys():
            if player_raw.lower() in k.lower() or k.lower() in player_raw.lower():
                matched_key=k
                break
        # Try full_name if provided
        if not matched_key and "full_name" in entry:
            fn=entry["full_name"]
            if fn in stats_cache:
                matched_key=fn
            else:
                for k in stats_cache.keys():
                    if fn.lower() in k.lower() or k.lower() in fn.lower():
                        matched_key=k
                        break

    stats_entry=stats_cache.get(matched_key, {}) if matched_key else {}
    career_stats=stats_entry.get("career_stats", [])

    # For award year 2026 (season 2025-26)
    goals, apps, matches = find_stats_for_year(career_stats, 2026)

    # For Mbappé we have stats: 31 apps 25 goals league, plus Europe 15 etc total 42
    # For others, we may not have 2025-26 stats yet if Wikipedia not updated, but we have some
    print(f"{player_raw}: matched_key={matched_key}, goals={goals}, apps={apps}, matches={len(matches)}")

    # Trophy flags for 2026
    # UCL 2025-26 winner PSG
    ucl_winner=1 if "Paris Saint-Germain" in entry["club"] or "PSG" in entry["club"] else 0
    # Actually need check: UCL winner 2025-26 is PSG per our trophy list year 2026
    # So any PSG player gets ucl_winner=1

    # Adjust for actual UCL map
    # From earlier, UCL year 2026 winner PSG
    ucl_winner_flag = 1 if entry["club"] in ["Paris Saint-Germain"] or "Paris" in entry["club"] else 0
    # For Bayern, Barcelona etc not

    # World Cup 2026 winner Spain
    wc_winner_flag = 1 if entry["nation"]=="Spain" else 0

    # Club prestige
    prestige_tier_1={"Real Madrid","Barcelona","Bayern Munich","Manchester City","Paris Saint-Germain","Manchester United","Juventus","Milan","Liverpool","Inter","Chelsea"}
    prestige_score=3 if entry["club"] in prestige_tier_1 else 2 if entry["club"] in ["Arsenal","Atletico Madrid","Dortmund"] else 1
    prestige_tier=1 if prestige_score==3 else 2 if prestige_score==2 else 3

    # Position group
    pos=entry["position"].lower()
    if "forward" in pos:
        pos_group="forward"
        is_forward=1
        is_defender=0
        is_mid=0
        is_gk=0
    elif "midfield" in pos:
        pos_group="midfielder"
        is_forward=0
        is_defender=0
        is_mid=1
        is_gk=0
    elif "defender" in pos:
        pos_group="defender"
        is_forward=0
        is_defender=1
        is_mid=0
        is_gk=0
    elif "goalkeeper" in pos or "keeper" in pos:
        pos_group="goalkeeper"
        is_forward=0
        is_defender=0
        is_mid=0
        is_gk=1
    else:
        pos_group="unknown"
        is_forward=is_defender=is_mid=is_gk=0

    # Signature moment: if UCL winner or WC winner
    sig_flag=1 if (ucl_winner_flag or wc_winner_flag) else 0

    # For goals percentile, we need to compute within this 20-player pool after we have all goals
    rec={
        "player":player_raw,
        "club":entry["club"],
        "nation":entry["nation"],
        "position":entry["position"],
        "position_group":pos_group,
        "league_goals":goals,
        "league_apps":apps,
        "ucl_winner":ucl_winner_flag,
        "nation_won_world_cup":wc_winner_flag,
        "nation_won_any":wc_winner_flag,  # only WC for 2026
        "club_prestige_score":prestige_score,
        "club_prestige_tier":prestige_tier,
        "signature_moment_flag":sig_flag,
        "is_forward":is_forward,
        "is_defender":is_defender,
        "is_midfielder":is_mid,
        "is_goalkeeper":is_gk,
        "is_missing_stats":1 if goals is None else 0,
        "rank_givemesport":entry["rank_givemesport"]
    }
    records.append(rec)

df_live=pd.DataFrame(records)
print("\nLive raw records:")
print(df_live[["player","league_goals","league_apps","ucl_winner","nation_won_world_cup","club_prestige_score"]].to_string())

# For missing goals, impute median per position
for col in ["league_goals","league_apps"]:
    median=df_live[col].median()
    df_live[col]=df_live[col].fillna(median if pd.notna(median) else 0)

# Compute percentile within this pool
df_live["goals_percentile"] = df_live["league_goals"].rank(pct=True)*100
df_live["goals_per_app"] = df_live["league_goals"]/df_live["league_apps"].replace(0,1)
df_live["goals_per_app_percentile"] = df_live["goals_per_app"].rank(pct=True)*100

# Save
out_path=BASE/"data/processed/live_2026_features.csv"
df_live.to_csv(out_path, index=False)
print(f"\nSaved live 2026 features to {out_path}")

# Now predict using Tier B model
import pickle, yaml
from pathlib import Path as Path2
BASE2=Path2(__file__).parent.parent
MODEL_B_PATH=BASE2/"models/tier_b_model.pkl"
SCALER_B_PATH=BASE2/"models/tier_b_scaler.pkl"
FEATURES_USED_PATH=BASE2/"data/processed/tier_b_features_used.json"

import json
with open(FEATURES_USED_PATH) as f:
    feat_info=json.load(f)
feature_cols=feat_info["features"]

with open(MODEL_B_PATH,'rb') as f:
    model=pickle.load(f)
with open(SCALER_B_PATH,'rb') as f:
    scaler=pickle.load(f)

# Map our live df columns to feature cols expected
# Feature cols from Tier B: goals_percentile_in_year, ucl_winner, league_winner, nation_won_any_international, club_prestige_score, signature_moment_flag, is_forward, is_defender, is_goalkeeper, is_missing_stats, is_world_cup_year
# We have: goals_percentile (use as goals_percentile_in_year), ucl_winner, league_winner not available (set 0), nation_won_any, club_prestige_score, signature_moment_flag, is_forward etc, is_missing_stats, is_world_cup_year (2026 is WC year)

df_live["goals_percentile_in_year"]=df_live["goals_percentile"]
df_live["league_winner"]=0  # not computed for 2026 yet, could add but set 0
df_live["nation_won_any_international"]=df_live["nation_won_world_cup"]
df_live["is_world_cup_year"]=1  # 2026 is WC year
df_live["is_missing_stats"]=df_live["is_missing_stats"]

# Ensure all feature cols present
for col in feature_cols:
    if col not in df_live.columns:
        df_live[col]=0

X=df_live[feature_cols].values
# Impute any remaining NaN with 0
import numpy as np
X=np.nan_to_num(X, nan=0.0)

X_scaled=scaler.transform(X)
scores=np.dot(X_scaled, model.coef_.T).flatten()
df_live["tier_b_score"]=scores
df_live["predicted_rank"]=df_live["tier_b_score"].rank(ascending=False, method='min')
df_live_sorted=df_live.sort_values("predicted_rank")

print("\n=== Predicted Ranking for 2026 Ballon d'Or (Live, 20 contenders from givemesport July 20 2026) ===")
for _, row in df_live_sorted.iterrows():
    print(f"{int(row['predicted_rank'])}. {row['player']} ({row['club']}, {row['nation']}, {row['position']}) - score {row['tier_b_score']:.3f} - goals {row['league_goals']} - UCL winner {row['ucl_winner']} - WC winner {row['nation_won_world_cup']} - prestige {row['club_prestige_score']} - givemesport rank {row['rank_givemesport']}")

# Save prediction
out_pred=BASE/"reports/live_prediction_2026.json"
output={
    "season_id":"2026",
    "generated_at":pd.Timestamp.now().isoformat(),
    "model_version":"tier_b_linear_ranker_v1",
    "source_shortlist":"https://www.givemesport.com/ballon-dor-power-rankings/ (20 contenders July 20 2026)",
    "world_cup_2026_winner":"Spain (beat Argentina 1-0 final, per AS.com and Wikipedia)",
    "ucl_2025_26_winner":"Paris Saint-Germain (per trophy_ucl.parquet year 2026)",
    "rankings":df_live_sorted[["player","club","nation","position","league_goals","league_apps","ucl_winner","nation_won_world_cup","club_prestige_score","tier_b_score","predicted_rank","rank_givemesport"]].to_dict(orient="records")
}
import json as js
with open(out_pred,'w') as f:
    js.dump(output, f, indent=2)

print(f"\nSaved live prediction to {out_pred}")
