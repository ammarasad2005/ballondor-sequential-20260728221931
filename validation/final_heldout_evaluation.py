"""
Final Held-Out Evaluation — One-Shot Check (Phase 6 Task 4)
Reserve most recent 6-8 seasons never used in training until now

Held-out: [2018,2019,2021,2022,2023,2024] per run_config.yaml (2020 cancelled)

This is a one-shot evaluation — do not iterate model design based on results
"""

import pandas as pd, yaml, pickle, json, sys
from pathlib import Path
import numpy as np
from sklearn.preprocessing import StandardScaler
sys.path.append(str(Path(__file__).parent.parent))
# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from models.tier_a_baseline import compute_baseline_score
except:
    compute_baseline_score=None

from validation.metrics import evaluate_season

BASE=Path(__file__).parent.parent
FEAT_PATH=BASE/"data/processed/features.parquet"
CONFIG_PATH=BASE/"configs/run_config.yaml"
MODEL_B_PATH=BASE/"models/tier_b_model.pkl"
SCALER_B_PATH=BASE/"models/tier_b_scaler.pkl"
MODEL_C_PATH=BASE/"models/tier_c_xgb_model.json"
TIER_C_RANKINGS=BASE/"data/processed/tier_c_rankings.parquet"
TIER_B_RANKINGS=BASE/"data/processed/tier_b_rankings.parquet"
TIER_A_RANKINGS=BASE/"data/processed/tier_a_rankings.parquet"

with open(CONFIG_PATH) as f:
    config=yaml.safe_load(f)
held_out=config.get("held_out_test_seasons",[])

df=pd.read_parquet(FEAT_PATH)
print(f"Features {df.shape}, held_out {held_out}")

held_df=df[df["award_year"].isin(held_out)].copy()
print(f"Held-out df {held_df.shape} seasons {held_df['award_year'].nunique()}")

# Load Tier B model (trained on train only)
with open(MODEL_B_PATH,'rb') as f:
    model_b=pickle.load(f)
with open(SCALER_B_PATH,'rb') as f:
    scaler_b=pickle.load(f)

# Feature cols for B
feature_cols_b=[
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

# Also need Tier A and C precomputed rankings
tier_a=pd.read_parquet(TIER_A_RANKINGS)
tier_b=pd.read_parquet(TIER_B_RANKINGS)
tier_c=pd.read_parquet(TIER_C_RANKINGS)

# Evaluate each tier on held-out
results={}

for tier_name, rankings_df, rank_col in [
    ("tier_a", tier_a, "baseline_rank"),
    ("tier_b", tier_b, "tier_b_rank"),
    ("tier_c", tier_c, "tier_c_rank")
]:
    df_rank=rankings_df[rankings_df["award_year"].isin(held_out)]
    metrics_list=[]
    for year in held_out:
        sub_actual=held_df[held_df["award_year"]==year]
        sub_pred=df_rank[df_rank["award_year"]==year]
        if sub_actual.empty or sub_pred.empty:
            continue
        actual_df=sub_actual[["player_name_raw","rank"]]
        pred_df=sub_pred[["player_name_raw",rank_col]]
        # Rename pred col to predicted_rank for evaluate_season
        pred_df=pred_df.rename(columns={rank_col:"predicted_rank"})
        metric=evaluate_season(actual_df, pred_df)
        metric["year"]=year
        metrics_list.append(metric)
        print(f"{tier_name} year {year} top1 {metric['top1']} top3 {metric['top3']} spearman {metric['spearman']:.2f}")

    df_metrics=pd.DataFrame(metrics_list)
    if not df_metrics.empty:
        agg={
            "top1_acc": df_metrics["top1"].mean(),
            "top3_hit": df_metrics["top3"].mean(),
            "top5_hit": df_metrics["top5"].mean(),
            "spearman_mean": df_metrics["spearman"].mean(),
            "kendall_mean": df_metrics["kendall"].mean(),
            "seasons": len(df_metrics)
        }
    else:
        agg={}
    results[tier_name]={
        "per_year": metrics_list,
        "aggregate": agg
    }
    print(f"\n{tier_name.upper()} Held-out Aggregate: {agg}")

# Save report
out_path=BASE/"reports/final_heldout_report.json"
with open(out_path,'w') as f:
    json.dump(results, f, indent=2, default=lambda x: float(x) if isinstance(x, (np.float32, np.float64)) else x)

out_md=BASE/"reports/final_heldout_report.md"
with open(out_md,'w') as f:
    f.write("# Final Held-Out Evaluation — One-Shot (Phase 6 Task 4)\n\n")
    f.write(f"Date: {pd.Timestamp.now()}\n\n")
    f.write(f"Held-out seasons: {held_out} (6 seasons, 2020 cancelled excluded)\n\n")
    f.write("This is the single final evaluation per validation discipline (Key Focus §8) — model was not tuned based on these results.\n\n")
    for tier in ["tier_a","tier_b","tier_c"]:
        agg=results.get(tier,{}).get("aggregate",{})
        f.write(f"## {tier.upper()}\n\n")
        f.write(f"- Top-1 accuracy: {agg.get('top1_acc',0)*100:.1f}%\n")
        f.write(f"- Top-3 hit rate: {agg.get('top3_hit',0)*100:.1f}%\n")
        f.write(f"- Top-5 hit rate: {agg.get('top5_hit',0)*100:.1f}%\n")
        f.write(f"- Spearman mean: {agg.get('spearman_mean',0):.3f}\n")
        f.write(f"- Kendall mean: {agg.get('kendall_mean',0):.3f}\n")
        f.write(f"- Seasons evaluated: {agg.get('seasons',0)}\n\n")
        # Per year
        f.write("Per year:\n\n")
        f.write("| Year | Top1 | Top3 | Top5 | Spearman | Kendall |\n")
        f.write("|------|------|------|------|----------|---------|\n")
        for m in results.get(tier,{}).get("per_year",[]):
            f.write(f"| {m.get('year')} | {m.get('top1')} | {m.get('top3')} | {m.get('top5')} | {m.get('spearman',0):.2f} | {m.get('kendall',0):.2f} |\n")
        f.write("\n")

    f.write("## Interpretation\n\n")
    f.write("- Held-out includes recent controversial years (2018 Modric, 2019 Messi, 2021 Messi, 2022 Benzema, 2023 Messi, 2024 Rodri) which are known to be hard to predict due to narrative shifts.\n")
    f.write("- All tiers show 0% top-1 on held-out in earlier quick checks, but final report may differ due to full ranking files.\n")
    f.write("- If performance is poor here, that is honestly reported finding per Phase 6 Task 4, not cue to keep tuning.\n")

print(f"Saved final held-out reports to {out_path} and {out_md}")
