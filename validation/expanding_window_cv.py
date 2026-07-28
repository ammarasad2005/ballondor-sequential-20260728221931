"""
Expanding-Window Validation
Secondary, more realistic protocol: train only on seasons before year Y, predict year Y
Simulates real-world use case

Trains on non-held-out seasons only, in expanding window
"""

import pandas as pd, numpy as np, yaml
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import sys
sys.path.append(str(Path(__file__).parent.parent))
from validation.metrics import evaluate_season
from models.tier_a_baseline import compute_baseline_score

BASE=Path(__file__).parent.parent
FEAT_PATH=BASE/"data/processed/features.parquet"
CONFIG_PATH=BASE/"configs/run_config.yaml"

with open(CONFIG_PATH) as f:
    config=yaml.safe_load(f)
held_out=config.get("held_out_test_seasons",[])

df=pd.read_parquet(FEAT_PATH)
train_df=df[~df["award_year"].isin(held_out)].copy().sort_values("award_year")
print(f"Train for expanding window: {train_df['award_year'].nunique()} seasons")

feature_cols_tier_b=[
    "goals_percentile_in_year",
    "ucl_winner",
    "league_winner",
    "nation_won_any_international",
    "club_prestige_score",
    "signature_moment_flag",
    "is_forward",
    "is_defender",
    "is_goalkeeper",
    "is_missing_stats",
    "is_world_cup_year",
]

results_a=[]
results_b=[]

unique_years=sorted(train_df["award_year"].unique())
# Expanding window: start from maybe 1970 onwards to have enough training data (>10 seasons)
start_eval_year=1970

for eval_year in unique_years:
    if eval_year < start_eval_year:
        continue
    # Train on all seasons before eval_year
    train_split=train_df[train_df["award_year"]<eval_year]
    val_season=train_df[train_df["award_year"]==eval_year]

    if len(train_split)<10 or val_season.empty:
        continue

    print(f"\n=== Expanding window eval year {eval_year}, train size {len(train_split)} seasons {train_split['award_year'].nunique()} ===")

    # Tier A
    val_a=val_season.copy()
    val_a["baseline_score"]=compute_baseline_score(val_a)
    val_a["predicted_rank"]=val_a["baseline_score"].rank(ascending=False, method='min')
    actual_df=val_a[["player_name_raw","rank"]]
    pred_df=val_a[["player_name_raw","predicted_rank"]]
    metrics=evaluate_season(actual_df, pred_df)
    metrics["eval_year"]=eval_year
    metrics["era"]=val_a["era"].iloc[0] if not val_a.empty else "unknown"
    results_a.append(metrics)
    print(f"Tier A Top1 {metrics['top1']} Spearman {metrics['spearman']:.2f}")

    # Tier B
    # Generate pairwise from train_split
    X_pairs=[]
    y_pairs=[]
    for year in train_split["award_year"].unique():
        sub=train_split[train_split["award_year"]==year]
        if len(sub)<2:
            continue
        sub_filled=sub.copy()
        for col in feature_cols_tier_b:
            median=train_split[col].median()
            sub_filled[col]=sub_filled[col].fillna(median if not pd.isna(median) else 0)
        for idx_i, row_i in sub_filled.iterrows():
            for idx_j, row_j in sub_filled.iterrows():
                if idx_i==idx_j:
                    continue
                label=1 if row_i["rank"]<row_j["rank"] else 0
                diff=[row_i[col]-row_j[col] for col in feature_cols_tier_b]
                X_pairs.append(diff)
                y_pairs.append(label)

    if not X_pairs:
        continue

    X=np.array(X_pairs)
    y=np.array(y_pairs)
    scaler=StandardScaler()
    X_scaled=scaler.fit_transform(X)
    model=LogisticRegression(penalty='l2', C=0.5, solver='lbfgs', max_iter=500, random_state=42)
    model.fit(X_scaled, y)

    val_b=val_season.copy()
    for col in feature_cols_tier_b:
        median=train_split[col].median()
        val_b[col]=val_b[col].fillna(median if not pd.isna(median) else 0)
    X_val=val_b[feature_cols_tier_b].values
    X_val_scaled=scaler.transform(X_val)
    scores=np.dot(X_val_scaled, model.coef_.T).flatten()
    val_b["tier_b_score"]=scores
    val_b["predicted_rank"]=val_b["tier_b_score"].rank(ascending=False, method='min')
    actual_df=val_b[["player_name_raw","rank"]]
    pred_df=val_b[["player_name_raw","predicted_rank"]]
    metrics_b=evaluate_season(actual_df, pred_df)
    metrics_b["eval_year"]=eval_year
    metrics_b["era"]=val_b["era"].iloc[0] if not val_b.empty else "unknown"
    results_b.append(metrics_b)
    print(f"Tier B Top1 {metrics_b['top1']} Spearman {metrics_b['spearman']:.2f}")

# Aggregate
for tier_name, res in [("Tier A", results_a), ("Tier B", results_b)]:
    df_res=pd.DataFrame(res)
    if df_res.empty:
        continue
    print(f"\n=== {tier_name} Expanding Window Aggregate ===")
    print(f"Seasons evaluated {len(df_res)}")
    print(f"Top-1 {df_res['top1'].mean()*100:.1f}%")
    print(f"Top-3 {df_res['top3'].mean()*100:.1f}%")
    print(f"Top-5 {df_res['top5'].mean()*100:.1f}%")
    print(f"Spearman {df_res['spearman'].mean():.3f}")

# Save
import json
out_json=BASE/"reports/expanding_window_report.json"
with open(out_json,'w') as f:
    json.dump({"tier_a":results_a, "tier_b":results_b}, f, indent=2, default=lambda x: float(x) if isinstance(x, (np.float32, np.float64)) else x)

out_md=BASE/"reports/expanding_window_report.md"
with open(out_md,'w') as f:
    f.write("# Expanding Window Validation Report\n\n")
    f.write(f"Held-out excluded: {held_out}\n\n")
    for tier_name, res in [("Tier A", results_a), ("Tier B", results_b)]:
        df_res=pd.DataFrame(res)
        if df_res.empty:
            continue
        f.write(f"## {tier_name}\n\n")
        f.write(f"- Seasons evaluated: {len(df_res)}\n")
        f.write(f"- Top-1: {df_res['top1'].mean()*100:.1f}%\n")
        f.write(f"- Top-3: {df_res['top3'].mean()*100:.1f}%\n")
        f.write(f"- Top-5: {df_res['top5'].mean()*100:.1f}%\n")
        f.write(f"- Spearman: {df_res['spearman'].mean():.3f}\n")
        f.write(f"- Kendall: {df_res['kendall'].mean():.3f}\n\n")

print("Saved expanding window reports")
