"""
Phase 1 QA and spot-check script
"""

import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent.parent
GT_PATH = BASE / "data" / "processed" / "ground_truth.parquet"
EVAL_PATH = BASE / "data" / "processed" / "eval_window_metadata.csv"

df = pd.read_parquet(GT_PATH)
print(f"Loaded ground truth: {df.shape} rows, {df['award_year'].nunique()} seasons")

# QA checks
print("\n=== QA Checks ===")
# 1. Every year has winner rank 1
missing_winner = []
for year in df["award_year"].unique():
    sub = df[df["award_year"]==year]
    if 1 not in sub["rank"].values:
        missing_winner.append(year)
print(f"Years missing winner rank 1: {missing_winner if missing_winner else 'None PASS'}")

# 2. No duplicate players per year
dup_years = []
for year in df["award_year"].unique():
    sub = df[df["award_year"]==year]
    if sub["player_name_raw"].duplicated().any():
        dups = sub[sub["player_name_raw"].duplicated(keep=False)]["player_name_raw"].tolist()
        dup_years.append((year, dups))
print(f"Duplicate players per year: {dup_years if dup_years else 'None PASS'}")

# 3. Rank contiguous check: ranks should be 1..max without major gaps? Allow tied ranks? But check for gaps
gap_warnings = []
for year in sorted(df["award_year"].unique()):
    sub = df[df["award_year"]==year].sort_values("rank")
    ranks = sub["rank"].tolist()
    max_rank = max(ranks)
    # Expected set if no ties: 1..max but if duplicates due to ties, allow? For Ballon d'Or ties sometimes occur (joint positions). Let's check max vs count
    # If counts different, check missing numbers
    expected_set = set(range(1, max_rank+1))
    actual_set = set(ranks)
    missing = expected_set - actual_set
    if missing:
        gap_warnings.append((year, f"missing ranks {sorted(missing)}", f"count {len(ranks)} max {max_rank}"))
print(f"Rank gap warnings (may be ties or incomplete data): {gap_warnings[:20]}")
if not gap_warnings:
    print("PASS: No rank gaps detected (contiguous 1..N)")

# 4. Points non-increasing with rank (where points available)
# Just sample check, not failing
points_warnings = []
for year in sorted(df["award_year"].unique()):
    sub = df[df["award_year"]==year].dropna(subset=["points"]).sort_values("rank")
    if len(sub) < 2:
        continue
    pts = sub["points"].tolist()
    # Points should generally decrease as rank increases (higher rank = lower points)
    # Allow small increase due to different voting systems? Check major inversion
    for i in range(1, len(pts)):
        if pts[i] > pts[i-1] + 0.01:  # increasing with worse rank => inversion
            points_warnings.append((year, sub.iloc[i-1]["rank"], sub.iloc[i-1]["points"], sub.iloc[i]["rank"], sub.iloc[i]["points"]))
            break

print(f"Points non-increasing violations (sample): {points_warnings[:10] if points_warnings else 'None PASS'}")

# 5. Row counts per year
print("\nRow counts per year:")
counts = df.groupby("award_year").size()
print(counts.describe())
print(counts.tail(15))

# 6. Eval window metadata existence
eval_df = pd.read_csv(EVAL_PATH)
print(f"\nLoaded eval metadata: {eval_df.shape}")
print(eval_df.head())

# Merge check: every ground_truth row should have eval period
missing_eval = df[df["eval_period_start"].isna() | df["eval_period_end"].isna()]
print(f"Rows missing eval period: {len(missing_eval)} (should be 0 except 2020 already excluded)")

# Check known controversial years
print("\n=== Known Cases Spot Check ===")
for year in [1956, 2022, 2023, 2024, 2025]:
    if year in df["award_year"].values:
        sub = df[df["award_year"]==year].sort_values("rank").head(5)
        print(f"\n{year} top5:")
        print(sub[["rank","player_name_raw","club_at_time","points"]].to_string(index=False))

# Output summary for PROJECT_LOG
print("\n=== Summary for Phase 1 ===")
print(f"Total seasons: {df['award_year'].nunique()}, total rows: {len(df)}")
print(f"Years covered: {sorted(df['award_year'].unique())[:5]} ... {sorted(df['award_year'].unique())[-5:]}")
print(f"2020 cancelled present? {'2020' in df['season_id'].unique()}")
print(f"Average rows/year: {len(df)/df['award_year'].nunique():.2f}")
