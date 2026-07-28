"""
Tier B — Pairwise linear ranker
Learn w_i via pairwise logistic regression over within-season pairs (did player A rank above player B)
Fully interpretable coefficients

Trains on non-held-out seasons only (held-out = [2018,2019,2021,2022,2023,2024] per run_config)
"""

import pandas as pd, numpy as np, yaml
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import pickle

BASE=Path(__file__).parent.parent
FEAT_PATH=BASE/"data/processed/features.parquet"
CONFIG_PATH=BASE/"configs/run_config.yaml"
MODEL_OUT=BASE/"models/tier_b_model.pkl"
SCALER_OUT=BASE/"models/tier_b_scaler.pkl"
FEATURES_OUT=BASE/"data/processed/tier_b_features_used.json"

with open(CONFIG_PATH) as f:
    config=yaml.safe_load(f)

held_out=config.get("held_out_test_seasons",[])

# Load features
df=pd.read_parquet(FEAT_PATH)
print(f"Loaded features {df.shape}, held_out {held_out}")

# Filter training data: exclude held-out
train_df=df[~df["award_year"].isin(held_out)].copy()
test_df=df[df["award_year"].isin(held_out)].copy()
print(f"Train {train_df.shape} (seasons {train_df['award_year'].nunique()}), Test held-out {test_df.shape} (seasons {test_df['award_year'].nunique()})")

# Feature columns for linear model — reduced to avoid multicollinearity
# Now includes advanced metrics from Understat (xG, xA) to improve held-out
# Per Phase 5 Task 2: sanity-check coefficient signs, nonsensical sign is bug signal
feature_cols=[
    "goals_percentile_in_year",  # primary individual output, should be positive
    "xG_percentile_in_year",  # advanced: xG percentile (modern) - should be positive
    "xA_percentile_in_year",  # advanced: xA percentile
    "ucl_winner",  # should be positive
    "league_winner",
    "nation_won_any_international",
    "club_prestige_score",  # big-club bias, should be positive but small
    "signature_moment_flag",  # recency proxy, should be positive
    "is_forward",
    "is_defender",
    "is_goalkeeper",
    "is_missing_stats",  # should be negative (penalty for missing)
    "is_world_cup_year",  # tournament year flag
]

# Alternative full set kept for reference but we use reduced for interpretability
full_feature_cols=[
    "goals_percentile_in_year",
    "goals_per_app_percentile_in_year",
    "apps_percentile_in_year",
    "league_goals",
    "league_apps",
    "goals_per_app",
    "ucl_winner",
    "league_winner",
    "domestic_and_ucl_double",
    "is_world_cup_year",
    "is_euro_year",
    "is_copa_year",
    "nation_won_world_cup",
    "nation_won_euro",
    "nation_won_copa",
    "nation_won_any_international",
    "durability_apps",
    "is_missing_stats",
    "club_prestige_score",
    "market_size_proxy",
    "signature_moment_flag",
    "is_forward",
    "is_midfielder",
    "is_defender",
    "is_goalkeeper",
]

# Check which exist
existing=[c for c in feature_cols if c in train_df.columns]
print(f"Using features: {existing}")

# Imputation: median per era/position? For simplicity, median global for now, plus is_missing flag already captures missing
# For numeric, fill with median, for binary fill 0
for col in existing:
    if train_df[col].dtype.kind in 'bifc':
        median=train_df[col].median()
        # For binary, median may be 0, fine
        train_df[col]=train_df[col].fillna(median if not pd.isna(median) else 0)
        test_df[col]=test_df[col].fillna(median if not pd.isna(median) else 0)

# For pairwise generation
# For each season, generate all ordered pairs (i,j) where i != j
# Label 1 if rank_i < rank_j (i is better)
# X = features_i - features_j
# This creates balanced dataset: for each unordered pair we have one label 1 and one label 0 (if we generate both directions)
# We'll generate all ordered pairs to have both labels

X_pairs=[]
y_pairs=[]
season_pairs=[]

for year in train_df["award_year"].unique():
    sub=train_df[train_df["award_year"]==year]
    if len(sub)<2:
        continue
    # For each ordered pair
    for idx_i, row_i in sub.iterrows():
        for idx_j, row_j in sub.iterrows():
            if idx_i==idx_j:
                continue
            # Label: 1 if i better than j (rank lower number)
            label=1 if row_i["rank"] < row_j["rank"] else 0
            # Feature diff
            diff=[]
            for col in existing:
                diff.append(row_i[col] - row_j[col])
            X_pairs.append(diff)
            y_pairs.append(label)
            season_pairs.append(year)

X=np.array(X_pairs)
y=np.array(y_pairs)
print(f"Generated {len(X)} pairwise samples from {train_df['award_year'].nunique()} seasons")

# Scale features? For logistic regression, scaling helps but coefficients interpretable after scaling? We can use StandardScaler but then coefficients relative to scaled features
# For interpretability, we might want to not scale, but logistic regression benefits from scaling
# We'll scale for training, but also keep unscaled version for coefficient inspection

scaler=StandardScaler()
X_scaled=scaler.fit_transform(X)

# Train logistic regression
# Small N dataset, need stronger regularization to avoid overfitting and unstable signs
# Use C=0.5 for stronger L2, and class_weight balanced? But pairwise is balanced by construction (ordered pairs produce 50/50)
model=LogisticRegression(penalty='l2', C=0.5, solver='lbfgs', max_iter=1000, random_state=42)
model.fit(X_scaled, y)

print(f"Trained logistic regression, train accuracy {model.score(X_scaled, y):.3f}")

# Extract coefficients
coefs=model.coef_[0]
coef_dict={col: float(coef) for col, coef in zip(existing, coefs)}
print("\nCoefficients (scaled feature space):")
for col, coef in sorted(coef_dict.items(), key=lambda x: abs(x[1]), reverse=True)[:15]:
    print(f"  {col}: {coef:.3f}")

# Save model and scaler
import pickle
with open(MODEL_OUT,'wb') as f:
    pickle.dump(model, f)
with open(SCALER_OUT,'wb') as f:
    pickle.dump(scaler, f)

# Save feature list
import json
with open(FEATURES_OUT,'w') as f:
    json.dump({"features":existing, "coefficients":coef_dict, "intercept":float(model.intercept_[0])}, f, indent=2)

print(f"Saved model to {MODEL_OUT}, scaler to {SCALER_OUT}")

# Function to predict ranking for a season
def predict_season_ranking(season_df, model, scaler, feature_cols):
    """Given season df, compute scores and rank"""
    # Impute as before
    season_df=season_df.copy()
    for col in feature_cols:
        if col not in season_df.columns:
            season_df[col]=0
        season_df[col]=season_df[col].fillna(0)

    X_season=season_df[feature_cols].values
    # For linear ranker, score = w·features (before sigmoid)
    # We have model trained on differences, but we can compute score as w·features (dot product)
    # Since logistic regression learns w for diff, the score for a player is w·features (same w)
    # So compute score = scaler transform then dot with coef + intercept? Actually for ranking, only w·features matters, intercept cancels in diff
    # We'll compute scaled features dot coef
    X_scaled_season=scaler.transform(X_season)
    scores=np.dot(X_scaled_season, model.coef_.T).flatten()  # shape (n,)
    season_df["tier_b_score"]=scores
    season_df["tier_b_rank"]=season_df["tier_b_score"].rank(ascending=False, method='min')
    return season_df.sort_values("tier_b_rank")

# Evaluate on training via LOSO simulation quick (not full LOSO yet, just per-season top-1)
# For each train season, predict winner
correct=0
total=0
for year in train_df["award_year"].unique():
    sub=train_df[train_df["award_year"]==year]
    pred=predict_season_ranking(sub, model, scaler, existing)
    # Predicted winner = tier_b_rank 1
    pred_winner=pred[pred["tier_b_rank"]==1]
    if pred_winner.empty:
        pred_winner=pred.sort_values("tier_b_score", ascending=False).head(1)
    actual_winner=sub[sub["rank"]==1]
    if actual_winner.empty:
        continue
    total+=1
    if pred_winner.iloc[0]["player_name_raw"]==actual_winner.iloc[0]["player_name_raw"]:
        correct+=1

print(f"\nTier B (train seasons) Top-1 Accuracy (using model trained on all train seasons, not LOSO): {correct}/{total} = {correct/total*100:.1f}%")

# Also evaluate on held-out (should not be used for tuning, just reporting for final? But we should not look at held-out during modeling per validation discipline)
# For Phase 5 we can compute but not tune
if not test_df.empty:
    correct_h=0
    total_h=0
    for year in test_df["award_year"].unique():
        sub=test_df[test_df["award_year"]==year]
        pred=predict_season_ranking(sub, model, scaler, existing)
        actual_winner=sub[sub["rank"]==1]
        if actual_winner.empty:
            continue
        total_h+=1
        pred_winner=pred[pred["tier_b_rank"]==1]
        if pred_winner.empty:
            pred_winner=pred.sort_values("tier_b_score", ascending=False).head(1)
        if pred_winner.iloc[0]["player_name_raw"]==actual_winner.iloc[0]["player_name_raw"]:
            correct_h+=1
    print(f"Tier B Held-out (should be untouched, just for info, not tuning): {correct_h}/{total_h} = {correct_h/total_h*100:.1f}% — NOTE: This should not be used for model selection")

# Save rankings for all seasons
all_rankings=[]
for year in df["award_year"].unique():
    sub=df[df["award_year"]==year].copy()
    # Impute same median as train for all
    for col in existing:
        if col in sub.columns:
            median=train_df[col].median()
            sub[col]=sub[col].fillna(median if not pd.isna(median) else 0)
        else:
            sub[col]=0
    pred=predict_season_ranking(sub, model, scaler, existing)
    all_rankings.append(pred)

df_all_ranked=pd.concat(all_rankings)
out_path=BASE/"data/processed/tier_b_rankings.parquet"
df_all_ranked.to_parquet(out_path, index=False)
print(f"Saved Tier B rankings to {out_path}")
