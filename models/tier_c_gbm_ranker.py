"""
Tier C — Gradient-boosted ranker (XGBoost rank:pairwise / rank:ndcg)
Higher capacity, higher overfitting risk given N≈2004 rows — must be regularized aggressively (shallow trees, strong L1/L2, small learning rate, early stopping on validation seasons)

Trains on non-held-out seasons only
"""

import pandas as pd, numpy as np, yaml, pickle, json
from pathlib import Path
import xgboost as xgb

BASE=Path(__file__).parent.parent
FEAT_PATH=BASE/"data/processed/features.parquet"
CONFIG_PATH=BASE/"configs/run_config.yaml"

with open(CONFIG_PATH) as f:
    config=yaml.safe_load(f)
held_out=config.get("held_out_test_seasons",[])

df=pd.read_parquet(FEAT_PATH)
print(f"Loaded features {df.shape}, held_out {held_out}")

train_df=df[~df["award_year"].isin(held_out)].copy()
test_df=df[df["award_year"].isin(held_out)].copy()
print(f"Train {train_df.shape} seasons {train_df['award_year'].nunique()}, Test {test_df.shape}")

# Feature columns — use reduced set same as Tier B for comparability, but also include full for GBM? GBM can handle more features, but still avoid too many
feature_cols=[
    "goals_percentile_in_year",
    "goals_per_app_percentile_in_year",
    "apps_percentile_in_year",
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
    "league_goals",
    "goals_per_app",
]

existing=[c for c in feature_cols if c in train_df.columns]
print(f"Using features {existing}")

# Impute
for col in existing:
    median=train_df[col].median()
    fill_val=median if not pd.isna(median) else 0
    train_df[col]=train_df[col].fillna(fill_val)
    test_df[col]=test_df[col].fillna(fill_val)

# For XGBoost ranking, need to sort by award_year and have groups
train_df=train_df.sort_values("award_year")
# Group sizes = number of candidates per season
group_sizes=train_df.groupby("award_year").size().tolist()
print(f"Group sizes (train): {group_sizes[:10]}")

# For ranking, we need to create relevance labels: lower rank (1) should have higher relevance
# Use inverse rank or points? We have rank 1..N, so relevance can be max_rank+1 - rank, or 1/rank, or use points? 
# Per P1, points are voting-system artifacts not comparable across eras, so use rank-based relevance: higher relevance for better rank
# For each season, compute relevance = N - rank +1 (so winner gets N, last gets 1)
# Or use exponential? Let's use N - rank +1

def compute_relevance(group):
    # group is df for one season
    max_rank=group["rank"].max()
    # relevance = max_rank - rank +1, capped at 31 to satisfy XGBoost ndcg_exp_gain requirement (when exp_gain True, must <=31)
    # Even with exp_gain False, capping keeps DCG manageable
    rel = max_rank - group["rank"] + 1
    # Cap at 31
    rel = rel.clip(upper=31) if hasattr(rel, 'clip') else min(rel, 31)
    return rel

train_df["relevance"]=train_df.groupby("award_year", group_keys=False).apply(lambda g: compute_relevance(g), include_groups=False)

# For validation during training, we need to split train into train/val for early stopping
# Use last 20% seasons as validation for early stopping, but not held-out
# Let's sort years and take last 10 seasons of train as val
unique_years=sorted(train_df["award_year"].unique())
n_val=max(1, int(len(unique_years)*0.2))
val_years=unique_years[-n_val:]
train_years=unique_years[:-n_val]
print(f"Val years for early stopping: {val_years}, Train years: {len(train_years)}")

train_split=train_df[train_df["award_year"].isin(train_years)]
val_split=train_df[train_df["award_year"].isin(val_years)]

print(f"Train split {train_split.shape}, Val split {val_split.shape}")

X_train=train_split[existing].values
y_train=train_split["relevance"].values
group_train=train_split.groupby("award_year").size().tolist()

X_val=val_split[existing].values
y_val=val_split["relevance"].values
group_val=val_split.groupby("award_year").size().tolist()

dtrain=xgb.DMatrix(X_train, label=y_train)
dtrain.set_group(group_train)

dval=xgb.DMatrix(X_val, label=y_val)
dval.set_group(group_val)

# Params with aggressive regularization per Blueprint §4.5 and Key Focus §5 (suspicion of complexity)
params={
    "objective": "rank:ndcg",  # try rank:ndcg for NDCG optimization, with ndcg_exp_gain false to allow relevance >1
    "tree_method": "hist",
    "eta": 0.05,  # small learning rate per aggressive regularization requirement
    "max_depth": 3,  # shallow depth
    "min_child_weight": 5,
    "subsample": 0.7,
    "colsample_bytree": 0.7,
    "lambda": 10,  # strong L2
    "alpha": 5,     # strong L1
    "eval_metric": ["ndcg@3", "ndcg@5"],
    "ndcg_exp_gain": False,
    "seed": 42
}

print("Training XGBoost ranker...")
evals=[(dtrain, 'train'), (dval, 'eval')]
model=xgb.train(
    params,
    dtrain,
    num_boost_round=500,
    evals=evals,
    early_stopping_rounds=30,
    verbose_eval=20
)

print(f"Best iteration {model.best_iteration}, best score {model.best_score}")

# Save model
model_path=BASE/"models/tier_c_xgb_model.json"
model.save_model(model_path)
print(f"Saved model to {model_path}")

# Feature importance
importance=model.get_score(importance_type='gain')
print("\nFeature importance (gain):")
# Map feature index to name
for idx, name in enumerate(existing):
    # xgboost feature names are f0, f1 etc if not provided
    score=importance.get(f"f{idx}", 0)
    print(f"  {name}: {score:.2f}")

# Predict ranking for all seasons
df_all=df.copy()
for col in existing:
    median=train_df[col].median()
    df_all[col]=df_all[col].fillna(median if not pd.isna(median) else 0)

df_all=df_all.sort_values("award_year")
# For prediction, we need to create DMatrix per season? Actually we can predict all at once
X_all=df_all[existing].values
dall=xgb.DMatrix(X_all)
scores=model.predict(dall)
df_all["tier_c_score"]=scores

# Rank per season descending score
df_all["tier_c_rank"]=df_all.groupby("award_year")["tier_c_score"].rank(ascending=False, method='min')

out_path=BASE/"data/processed/tier_c_rankings.parquet"
df_all.to_parquet(out_path, index=False)
print(f"Saved Tier C rankings to {out_path}")

# Evaluate top-1 on train split
correct=0
total=0
for year in train_df["award_year"].unique():
    sub=df_all[df_all["award_year"]==year]
    actual=sub[sub["rank"]==1]
    pred=sub[sub["tier_c_rank"]==1]
    if actual.empty or pred.empty:
        continue
    total+=1
    if pred.iloc[0]["player_name_raw"]==actual.iloc[0]["player_name_raw"]:
        correct+=1
print(f"Tier C Train (all train seasons) Top-1: {correct}/{total} = {correct/total*100:.1f}%")

# Held-out evaluation (for info only, not tuning)
if not test_df.empty:
    correct_h=0
    total_h=0
    for year in test_df["award_year"].unique():
        sub=df_all[df_all["award_year"]==year]
        actual=sub[sub["rank"]==1]
        pred=sub[sub["tier_c_rank"]==1]
        if actual.empty or pred.empty:
            continue
        total_h+=1
        if pred.iloc[0]["player_name_raw"]==actual.iloc[0]["player_name_raw"]:
            correct_h+=1
    print(f"Tier C Held-out (info only): {correct_h}/{total_h} = {correct_h/total_h*100:.1f}%")
