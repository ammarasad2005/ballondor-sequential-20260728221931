"""
Feature Engineering Pipeline
Phase 4 — Builds features.parquet from ground_truth_resolved + stats + trophies + narrative

Implements all feature families per feature_registry.yaml
Outputs data/processed/features.parquet versioned schema
"""

import pandas as pd, json, re, os, yaml
from pathlib import Path
from datetime import datetime
import numpy as np

BASE=Path(__file__).parent.parent
GT_RESOLVED=BASE/"data/interim/ground_truth_resolved.parquet"
CANON=BASE/"data/interim/canonical_players.parquet"
STATS_COMBINED_DIR=BASE/"data/raw/stats_combined"
NARRATIVE=BASE/"data/processed/narrative_flags.parquet"
UCL=BASE/"data/processed/trophy_ucl.parquet"
WC=BASE/"data/processed/trophy_worldcup.parquet"
EUROS=BASE/"data/processed/trophy_euros.parquet"
COPA=BASE/"data/processed/trophy_copa.parquet"
DOMESTIC=BASE/"data/processed/trophy_domestic.parquet"
REGISTRY=BASE/"features/feature_registry.yaml"
EVAL_META=BASE/"data/processed/eval_window_metadata.csv"
OUTPUT=BASE/"data/processed/features.parquet"
OUTPUT_CSV=BASE/"data/processed/features.csv"

print("Loading data...")
gt=pd.read_parquet(GT_RESOLVED)
print(f"Ground truth resolved {gt.shape}")

narr=pd.read_parquet(NARRATIVE)
print(f"Narrative {narr.shape}")

# Load trophies
def load_trophy(path):
    try:
        return pd.read_parquet(path)
    except:
        # try csv fallback
        csv_path=path.with_suffix('.csv')
        if not path.exists():
            # try raw
            return pd.DataFrame()
        return pd.read_csv(csv_path)

ucl=load_trophy(UCL)
wc=load_trophy(WC)
euros=load_trophy(EUROS)
copa=load_trophy(COPA)
domestic=load_trophy(DOMESTIC)

print(f"Trophies loaded UCL {len(ucl)} WC {len(wc)} Euros {len(euros)} Copa {len(copa)} Domestic {len(domestic)}")

# Load eval metadata — handle season_id int vs str mismatch per Key Focus §1 bug fix
eval_meta=pd.read_csv(EVAL_META)
# Ensure season_id is string for consistent lookup, but also keep int version
eval_meta["season_id_str"] = eval_meta["season_id"].astype(str)
eval_meta["season_id_int"] = eval_meta["season_id"].astype(int)
# Create maps with both str and int keys
eval_map_str=eval_meta.set_index("season_id_str").to_dict('index')
eval_map_int=eval_meta.set_index("season_id_int").to_dict('index')
# Combined map: try both
eval_map={}
eval_map.update(eval_map_int)
eval_map.update(eval_map_str)
# For debugging, ensure 2023 exists
# print(f"Eval map keys sample: {list(eval_map.keys())[:5]}, has 2023? {2023 in eval_map} {'2023' in eval_map}")

# Build trophy maps for quick lookup
ucl_map={}
for _, row in ucl.iterrows():
    try:
        y=int(row["year"])
        ucl_map[y]=row["winner_club"]
    except:
        pass

wc_map={}
for _, row in wc.iterrows():
    try:
        y=int(row["year"])
        wc_map[y]=row["winner_country"]
    except:
        pass

euros_map={}
for _, row in euros.iterrows():
    try:
        y=int(row["year"])
        euros_map[y]=row["winner_country"]
    except:
        pass

copa_map={}
for _, row in copa.iterrows():
    try:
        y=int(row["year"])
        copa_map[y]=row["winner_country"]
    except:
        pass

# Domestic map: year -> list of winners (to check if player's club won any)
dom_year_to_winners={}
for _, row in domestic.iterrows():
    try:
        y=int(row["year"])
        winner=str(row["winner_club"])
        dom_year_to_winners.setdefault(y, []).append(winner)
    except:
        pass

print(f"Domestic year winners map size {len(dom_year_to_winners)}")

# Helper to parse season end year
def parse_season_end_year(season_str):
    if not season_str or pd.isna(season_str):
        return None
    s=str(season_str).strip()
    # Remove footnotes [xxx]
    s=re.sub(r'\[.*?\]','',s)
    s=s.strip()
    if s.lower()=="total":
        return None
    # Replace en dash with hyphen
    s=s.replace('–','-').replace('—','-')
    # Pattern: YYYY-YY or YYYY-YYYY or YYYY
    # e.g., "2003-04" -> end 2004
    # e.g., "2003-2004" -> end 2004
    # e.g., "2003" -> 2003
    # e.g., "2003/04"
    # Try to extract years
    # First, find all 4-digit years
    years_4=re.findall(r'\b(\d{4})\b', s)
    if len(years_4)>=2:
        # Take last as end year
        try:
            return int(years_4[-1])
        except:
            pass
    if len(years_4)==1:
        # Check if there's a 2-digit suffix after hyphen like "2003-04"
        m=re.search(r'(\d{4})[-/]\s*(\d{2})\b', s)
        if m:
            first=int(m.group(1))
            second_two=int(m.group(2))
            century=first//100
            second=century*100+second_two
            if second < first:
                second+=100
            return second
        # Otherwise just that year
        return int(years_4[0])
    # Try YYYY-YY pattern where first is 4-digit and second 2-digit
    m2=re.search(r'(\d{4})[-/]\s*(\d{2})\b', s)
    if m2:
        first=int(m2.group(1))
        second_two=int(m2.group(2))
        century=first//100
        second=century*100+second_two
        if second < first:
            second+=100
        return second
    # Try single year 2-digit? unlikely
    # Fallback: find any 4-digit via regex without word boundary
    m3=re.search(r'(\d{4})', s)
    if m3:
        return int(m3.group(1))
    return None

def find_stats_for_year(career_stats, award_year):
    """Find best matching career stats entries for award_year — robust version"""
    if not career_stats:
        return None, None, []

    # Filter career_stats to plausible entries first:
    # - season must not contain "total" or "career" (case insensitive)
    # - goals should be <=60 (no one scores >60 league goals in modern era, max ~50)
    # - apps <= 60 (max league games ~38-42)
    # - club not None and not purely navigational
    plausible=[]
    for entry in career_stats:
        season=str(entry.get("season","")).lower()
        if "total" in season or "career" in season:
            continue
        # Filter out extremely long season strings (like the Goal of Season Award list that concatenates many seasons)
        if len(season) > 30:
            continue
        club=entry.get("club")
        if not club or str(club).strip().lower() in ["none",""]:
            continue
        # Check goals/apps plausible
        g=entry.get("league_goals")
        a=entry.get("league_apps")
        # If goals > 80, likely parsing error (e.g., 1970, 2025)
        if g is not None:
            try:
                gv=int(g)
                if gv>60:  # unrealistic league goals in single season
                    continue
                if gv<0:
                    continue
            except:
                pass
        if a is not None:
            try:
                av=int(a)
                if av>60:
                    continue
                if av<0:
                    continue
            except:
                pass
        plausible.append(entry)

    # Now collect entries where end year == award_year (exact match)
    matches=[]
    for entry in plausible:
        season=entry.get("season")
        end_year=parse_season_end_year(season)
        if end_year==award_year:
            matches.append(entry)

    # If no exact end-year match, try with a small tolerance:
    # For calendar-year awards pre-2022, the relevant season could be the one ending in award_year or award_year+1 (since 2004 calendar includes part of 2004-05 season)
    # We'll allow end_year == award_year+1 as secondary, but only if no primary match
    if not matches:
        for entry in plausible:
            season=entry.get("season")
            end_year=parse_season_end_year(season)
            if end_year==award_year+1:
                # Only keep if season string starts with award_year (e.g., 2004-05 season starts 2004)
                # Check if start year == award_year
                s=str(entry.get("season",""))
                # Extract start year
                start_year=None
                years=re.findall(r'\b(\d{4})\b', s)
                if years:
                    try:
                        start_year=int(years[0])
                    except:
                        pass
                if start_year==award_year:
                    matches.append(entry)

    if not matches:
        return None, None, []

    # Sum goals/apps across matches (player may have multiple clubs in same season, e.g., loan)
    total_goals=0
    total_apps=0
    has_goals=False
    has_apps=False
    for m_entry in matches:
        g=m_entry.get("league_goals")
        a=m_entry.get("league_apps")
        if g is not None:
            try:
                total_goals+=int(g)
                has_goals=True
            except:
                pass
        if a is not None:
            try:
                total_apps+=int(a)
                has_apps=True
            except:
                pass
    goals=total_goals if has_goals else None
    apps=total_apps if has_apps else None
    return goals, apps, matches

# Load stats summary to get position and birth year quickly, but for per-season goals we need to read each player's combined JSON
# Preload all combined files into dict
print("Preloading stats combined files...")
stats_cache={}
for file in STATS_COMBINED_DIR.glob("*.json"):
    try:
        with open(file) as f:
            data=json.load(f)
        raw_name=data.get("player_name_raw")
        if raw_name:
            stats_cache[raw_name]=data
    except Exception as e:
        pass

print(f"Stats cache loaded {len(stats_cache)} players")

# Position grouping logic
def group_position(pos_raw):
    if not pos_raw or pd.isna(pos_raw):
        return "unknown"
    low=str(pos_raw).lower()
    # Goalkeeper
    if "goalkeeper" in low or "goal keeper" in low or low.strip()=="gk" or "keeper" in low:
        return "goalkeeper"
    # Defender: back, defender, libero, sweeper
    if any(x in low for x in ["defender", "back", "libero", "sweeper", "centre-back", "center-back", "centre back", "centrehalf"]):
        # But check if also contains forward/midfielder? Some like "Forward midfielder" should be forward, not defender
        # Prioritize forward
        if any(x in low for x in ["forward", "striker", "winger", "centre forward", "second striker"]):
            # If contains both defender and forward? Unlikely, but prioritize forward
            # Actually check if defender is primary
            # For simplicity, if contains "forward" or "striker" or "winger", treat as forward
            pass
        else:
            return "defender"
    # Midfielder
    if "midfielder" in low or "midfield" in low:
        # If also forward, but we already prioritized? For "Attacking midfielder forward", contains both forward and midfielder, we will treat as forward if forward present
        if any(x in low for x in ["forward", "striker", "winger"]):
            return "forward"
        return "midfielder"
    # Forward
    if any(x in low for x in ["forward", "striker", "winger", "centre forward", "second striker", "inside forward"]):
        return "forward"
    # Fallback
    return "unknown"

# Build features row by row - first pass raw extraction
records=[]
missing_stats_count=0
raw_goals_list=[]  # for median calc

for idx, row in gt.iterrows():
    season_id=str(row["season_id"])
    award_year=int(row["award_year"])
    player_raw=row["player_name_raw"]
    club=row.get("club_at_time")
    nation=row.get("nation_team")
    rank=int(row.get("rank",0))

    # Position from stats cache or resolved
    stats_entry=stats_cache.get(player_raw, {})
    pos_raw=stats_entry.get("position") or row.get("position_resolved")
    pos_group=group_position(pos_raw)

    # Individual production: league_goals, league_apps for award_year
    career_stats=stats_entry.get("career_stats", [])
    goals, apps, matched_entries=find_stats_for_year(career_stats, award_year)

    if goals is None and apps is None:
        missing_stats_count+=1
    else:
        if goals is not None:
            raw_goals_list.append(goals)

    goals_per_app=None
    if goals is not None and apps is not None and apps>0:
        try:
            goals_per_app=goals/apps
        except:
            pass

    # Trophy features
    ucl_winner_flag=0
    ucl_winner_name=ucl_map.get(award_year)
    if ucl_winner_name and club:
        if ucl_winner_name.lower() in str(club).lower() or str(club).lower() in ucl_winner_name.lower():
            ucl_winner_flag=1

    league_winner_flag=0
    winners_this_year=dom_year_to_winners.get(award_year, [])
    # Check if player's club matches any winner in that year (substring)
    if club and winners_this_year:
        for w in winners_this_year:
            if w.lower() in str(club).lower() or str(club).lower() in w.lower():
                league_winner_flag=1
                break

    domestic_and_ucl=1 if (ucl_winner_flag==1 and league_winner_flag==1) else 0

    # International tournament year flags
    is_wc_year=1 if award_year in wc_map else 0
    is_euro_year=1 if award_year in euros_map else 0
    is_copa_year=1 if award_year in copa_map else 0

    # Nation won flags: need eval window handling for season-based
    eval_info=eval_map.get(season_id, {})
    eval_type=eval_info.get("eval_type","calendar") if eval_info else "calendar"
    years_to_check=[award_year]
    if eval_type=="season":
        years_to_check.append(award_year-1)

    nation_won_wc=0
    nation_won_euro=0
    nation_won_copa=0
    for y_check in years_to_check:
        # WC
        wc_winner=wc_map.get(y_check)
        if wc_winner and nation:
            if str(nation).lower() in wc_winner.lower() or wc_winner.lower() in str(nation).lower():
                nation_won_wc=1
        # Euro
        euro_winner=euros_map.get(y_check)
        if euro_winner and nation:
            if str(nation).lower() in euro_winner.lower() or euro_winner.lower() in str(nation).lower():
                nation_won_euro=1
        # Copa
        copa_winner=copa_map.get(y_check)
        if copa_winner and nation:
            if str(nation).lower() in copa_winner.lower() or copa_winner.lower() in str(nation).lower():
                nation_won_copa=1

    nation_won_any=1 if (nation_won_wc or nation_won_euro or nation_won_copa) else 0

    # Availability
    durability=apps
    is_missing=int(1 if (goals is None and apps is None) else 0)

    # Narrative flags (join from narrative df)
    # Find matching row in narrative
    narr_row=narr[(narr["season_id"]==season_id) & (narr["player_name_raw"]==player_raw)]
    if not narr_row.empty:
        club_prestige_tier=narr_row.iloc[0]["club_prestige_tier"]
        club_prestige_score=narr_row.iloc[0]["club_prestige_score"]
        market_proxy=narr_row.iloc[0]["market_size_proxy"]
        sig_flag=narr_row.iloc[0]["signature_moment_flag"]
    else:
        club_prestige_tier=None
        club_prestige_score=None
        market_proxy=None
        sig_flag=0

    # Position binaries
    is_forward=1 if pos_group=="forward" else 0
    is_midfielder=1 if pos_group=="midfielder" else 0
    is_defender=1 if pos_group=="defender" else 0
    is_goalkeeper=1 if pos_group=="goalkeeper" else 0

    # Era tag
    if award_year >=2014:
        era="modern"
    else:
        era="classical"

    # Build record
    rec={
        "season_id":season_id,
        "award_year":award_year,
        "player_name_raw":player_raw,
        "player_name_canonical":row.get("player_name_canonical"),
        "canonical_id":row.get("canonical_id"),
        "rank":rank,
        "eval_period_start":row.get("eval_period_start"),
        "eval_period_end":row.get("eval_period_end"),
        "club_at_time":club,
        "nation_team":nation,
        "position_raw":pos_raw,
        "position_group":pos_group,
        "is_forward":is_forward,
        "is_midfielder":is_midfielder,
        "is_defender":is_defender,
        "is_goalkeeper":is_goalkeeper,
        "league_goals":goals,
        "league_apps":apps,
        "goals_per_app":goals_per_app,
        "durability_apps":durability,
        "is_missing_stats":is_missing,
        "ucl_winner":ucl_winner_flag,
        "league_winner":league_winner_flag,
        "domestic_and_ucl_double":domestic_and_ucl,
        "is_world_cup_year":is_wc_year,
        "is_euro_year":is_euro_year,
        "is_copa_year":is_copa_year,
        "nation_won_world_cup":nation_won_wc,
        "nation_won_euro":nation_won_euro,
        "nation_won_copa":nation_won_copa,
        "nation_won_any_international":nation_won_any,
        "club_prestige_tier":club_prestige_tier,
        "club_prestige_score":club_prestige_score,
        "market_size_proxy":market_proxy,
        "signature_moment_flag":sig_flag,
        "recency_boost_proxy":sig_flag,
        "era":era,
        "eval_type":eval_type,
        "source":"built from ground_truth_resolved + stats_combined + trophies + narrative"
    }
    records.append(rec)

print(f"Built {len(records)} feature records, missing stats count {missing_stats_count}")

df_features=pd.DataFrame(records)

# Improved imputation to reduce 27% missing per user request
# For modeling we want to fill missing league_goals/apps with median per era+position_group
# Keep is_missing_stats flag to indicate original gap (transparent per Key Focus §9)
print("\n=== Improved Imputation (median per era+position) to reduce missing ===")
# Compute median per era and position_group
for col in ["league_goals","league_apps","goals_per_app"]:
    # Overall median fallback
    overall_median=df_features[col].median()
    # Median per era
    era_median=df_features.groupby("era")[col].median()
    # Median per era+position
    era_pos_median=df_features.groupby(["era","position_group"])[col].median()

    def impute_row(row):
        if pd.notna(row[col]):
            return row[col]
        # Try era+position median
        try:
            key=(row["era"], row["position_group"])
            if key in era_pos_median and pd.notna(era_pos_median[key]):
                return era_pos_median[key]
        except:
            pass
        # Try era median
        try:
            if row["era"] in era_median and pd.notna(era_median[row["era"]]):
                return era_median[row["era"]]
        except:
            pass
        # Fallback overall median
        return overall_median

    # Create imputed column but also keep original missing flag
    # For now fill in place for modeling, but is_missing_stats retains original gap
    df_features[col+"_imputed_flag"] = df_features[col].isna().astype(int)
    df_features[col] = df_features.apply(impute_row, axis=1)
    # For goals_per_app, recalc if needed after imputation
    if col=="league_goals":
        # No recalc yet
        pass

# After imputation, recalculate goals_per_app if missing and now we have goals and apps
mask = df_features["goals_per_app"].isna() & df_features["league_goals"].notna() & df_features["league_apps"].notna() & (df_features["league_apps"]>0)
df_features.loc[mask, "goals_per_app"] = df_features.loc[mask, "league_goals"] / df_features.loc[mask, "league_apps"]

print(f"After imputation, missing league_goals: {df_features['league_goals'].isna().sum()}, league_apps {df_features['league_apps'].isna().sum()}")

# Peer-relative standing: compute percentile within each year's candidate pool per award_year
# For goals, apps, goals_per_app

def compute_percentile(series):
    # Rank percentile: (rank-1)/(n-1) *100, higher value = higher percentile
    # Use pandas rank pct
    # For missing values, keep NaN
    # Use method to handle ties: average
    return series.rank(pct=True, method='average')*100

# Group by award_year
for col in ["league_goals","league_apps","goals_per_app"]:
    pct_col=col+"_percentile_in_year" if col!="goals_per_app" else "goals_per_app_percentile_in_year"
    # For goals we need custom name per registry
    if col=="league_goals":
        pct_col="goals_percentile_in_year"
    elif col=="league_apps":
        pct_col="apps_percentile_in_year"

    df_features[pct_col]=df_features.groupby("award_year")[col].transform(lambda x: compute_percentile(x))

print("Computed peer-relative percentiles")

# Also compute additional derived: goals_percentile already done

# Sort
df_features=df_features.sort_values(["award_year","rank"])

# Save
df_features.to_parquet(OUTPUT, index=False)
df_features.to_csv(OUTPUT_CSV, index=False)
print(f"Saved features to {OUTPUT} shape {df_features.shape}")
print(f"Columns: {df_features.columns.tolist()}")

# Feature coverage report
print("\n=== Feature Coverage ===")
for col in ["league_goals","league_apps","goals_per_app","ucl_winner","league_winner","nation_won_any_international","club_prestige_tier","signature_moment_flag"]:
    missing=df_features[col].isna().sum()
    print(f"{col}: missing {missing}/{len(df_features)} ({missing/len(df_features)*100:.1f}%)")

print(f"\nEra distribution:\n{df_features['era'].value_counts()}")
print(f"Position group distribution:\n{df_features['position_group'].value_counts()}")

# Save feature registry validation: check which features are present
with open(REGISTRY) as f:
    reg=yaml.safe_load(f)
    declared=[feat["name"] for feat in reg["features"]]

print(f"\nDeclared features {len(declared)}, built columns {len(df_features.columns)}")
missing_declared=[d for d in declared if d not in df_features.columns and not d.startswith("xG") and not d.startswith("xA") and not d in ["progressive_passes","shot_creating_actions"]]
print(f"Declared but not built (excluding known missing advanced): {missing_declared[:20]}")
