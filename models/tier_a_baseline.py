"""
Tier A — Explicit weighted-sum baseline
Fully transparent formula with manually reasoned starting weights, not learned
Per Architecture Blueprint §4.5

Design rationale for weights (based on France Football criteria history and jury behavior):
- Criteria per 2022: 1) Individual performance decisive/impressive (most heavily), 2) Team success, 3) Fair play
- Historical jury: attacker overrepresentation, big-club bias, European competition bias, recency/narrative bias (P5)
- Weights reflect: goals (individual output) highest, then trophies, then narrative/prestige, then position bias as small adjustment

Formula:
score = sum(w_i * feature_i)

All features normalized to 0-100 scale where possible for comparability:
- Percentiles already 0-100
- Binary flags (ucl_winner etc) scaled *100
- club_prestige_score 1-3 scaled to 33/66/100

Weights sum to 1.0 for main components
"""

import pandas as pd
from pathlib import Path

BASE=Path(__file__).parent.parent
FEAT_PATH=BASE/"data/processed/features.parquet"

# Manually reasoned weights (not learned)
# Individual production: 50% of total weight (goals most important)
# Trophy/team success: 30%
# International + narrative: 20%

WEIGHTS={
    "goals_percentile_in_year": 0.30,  # primary individual output
    "goals_per_app_percentile_in_year": 0.15,  # efficiency
    "apps_percentile_in_year": 0.05,  # durability minor
    "ucl_winner": 0.15,  # UCL winner is highly predictive historically
    "league_winner": 0.07,
    "nation_won_any_international": 0.08,  # WC/Euro boost
    "club_prestige_score": 0.05,  # big-club bias modeled explicitly per P5
    "signature_moment_flag": 0.10,  # recency/narrative timing proxy
    # Position bonus handled separately as small additive bias, not weighted percentile
}

POSITION_BONUS={
    "forward": 5,      # attacker overrepresentation positive bias
    "midfielder": 0,
    "defender": -5,    # penalized by jury historically
    "goalkeeper": -10, # only Yashin won
    "unknown": 0
}

def compute_baseline_score(df):
    """Compute baseline score for each row in df"""
    # Ensure features exist, fill missing with 0 or median
    # For percentile features, missing -> 0 (lowest)
    # For binary flags, missing -> 0
    df = df.copy()
    for col in ["goals_percentile_in_year","goals_per_app_percentile_in_year","apps_percentile_in_year"]:
        df[col] = df[col].fillna(0)

    for col in ["ucl_winner","league_winner","nation_won_any_international","signature_moment_flag"]:
        df[col] = df[col].fillna(0)

    # club_prestige_score: 1-3, fill with 2 (tier2) median, then scale to 0-100
    df["club_prestige_score"] = df["club_prestige_score"].fillna(2)
    df["club_prestige_scaled"] = df["club_prestige_score"]/3*100

    # Compute weighted sum
    score = 0
    score += WEIGHTS["goals_percentile_in_year"] * df["goals_percentile_in_year"]
    score += WEIGHTS["goals_per_app_percentile_in_year"] * df["goals_per_app_percentile_in_year"]
    score += WEIGHTS["apps_percentile_in_year"] * df["apps_percentile_in_year"]
    score += WEIGHTS["ucl_winner"] * (df["ucl_winner"]*100)
    score += WEIGHTS["league_winner"] * (df["league_winner"]*100)
    score += WEIGHTS["nation_won_any_international"] * (df["nation_won_any_international"]*100)
    score += WEIGHTS["club_prestige_score"] * df["club_prestige_scaled"]
    score += WEIGHTS["signature_moment_flag"] * (df["signature_moment_flag"]*100)

    # Add position bonus
    pos_bonus = df["position_group"].map(POSITION_BONUS).fillna(0)
    score += pos_bonus

    return score

def main():
    df=pd.read_parquet(FEAT_PATH)
    df["baseline_score"]=compute_baseline_score(df)

    # For each season, rank by baseline_score descending (higher score = better rank)
    df["baseline_rank"]=df.groupby("award_year")["baseline_score"].rank(ascending=False, method='min')

    # Save
    out=BASE/"data/processed/tier_a_rankings.parquet"
    df_out=df[["season_id","award_year","player_name_raw","rank","baseline_score","baseline_rank","goals_percentile_in_year","ucl_winner","club_prestige_score","position_group"]]
    df_out.to_parquet(out, index=False)
    print(f"Saved Tier A rankings to {out} shape {df_out.shape}")

    # Quick evaluation: top-1 accuracy vs actual winner
    # Winner is rank 1 actual
    correct=0
    total=0
    for year in df["award_year"].unique():
        sub=df[df["award_year"]==year]
        if sub.empty:
            continue
        # Predicted winner: lowest baseline_rank (1)
        pred_winner=sub[sub["baseline_rank"]==1]
        if pred_winner.empty:
            # Tie? Take highest score
            pred_winner=sub.sort_values("baseline_score", ascending=False).head(1)
        actual_winner=sub[sub["rank"]==1]
        if actual_winner.empty:
            continue
        total+=1
        # Check if predicted player name matches actual (allow fuzzy? exact)
        pred_name=pred_winner.iloc[0]["player_name_raw"]
        actual_name=actual_winner.iloc[0]["player_name_raw"]
        if pred_name==actual_name:
            correct+=1
    print(f"Tier A Baseline Top-1 Accuracy: {correct}/{total} = {correct/total*100:.1f}%")

    # Also compute top-3 hit rate: is actual winner in top 3 predicted?
    top3_hit=0
    for year in df["award_year"].unique():
        sub=df[df["award_year"]==year]
        actual_winner=sub[sub["rank"]==1]
        if actual_winner.empty:
            continue
        actual_name=actual_winner.iloc[0]["player_name_raw"]
        top3_pred=sub[sub["baseline_rank"]<=3]["player_name_raw"].tolist()
        if actual_name in top3_pred:
            top3_hit+=1
    print(f"Top-3 hit rate: {top3_hit}/{total} = {top3_hit/total*100:.1f}%")

if __name__=="__main__":
    main()
