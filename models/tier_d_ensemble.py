"""
Tier D — Ensemble of Tier A and Tier B
Simple average-of-ranks ensemble per Architecture Blueprint §4.5
"""

import pandas as pd
import yaml
from pathlib import Path
import sys

BASE=Path(__file__).parent.parent
sys.path.append(str(BASE))

tier_a=BASE/"data/processed/tier_a_rankings.parquet"
tier_b=BASE/"data/processed/tier_b_rankings.parquet"

df_a=pd.read_parquet(tier_a)
df_b=pd.read_parquet(tier_b)

merged=pd.merge(
    df_a[["season_id","award_year","player_name_raw","baseline_rank","baseline_score"]],
    df_b[["season_id","award_year","player_name_raw","tier_b_rank","tier_b_score"]],
    on=["season_id","award_year","player_name_raw"],
    how="inner"
)

print(f"Merged {merged.shape}")

merged["ensemble_rank_avg"] = (merged["baseline_rank"] + merged["tier_b_rank"])/2
merged["ensemble_rank"] = merged.groupby("award_year")["ensemble_rank_avg"].rank(ascending=True, method='min')

def normalize_per_year(df, score_col):
    df["norm_"+score_col]=df.groupby("award_year")[score_col].transform(lambda x: (x - x.min())/(x.max()-x.min()+1e-9))
    return df

merged=normalize_per_year(merged, "baseline_score")
merged=normalize_per_year(merged, "tier_b_score")
merged["ensemble_score_norm"] = (merged["norm_baseline_score"] + merged["norm_tier_b_score"])/2
merged["ensemble_rank_score"] = merged.groupby("award_year")["ensemble_score_norm"].rank(ascending=False, method='min')
merged["final_ensemble_rank"] = merged["ensemble_rank"]

out_path=BASE/"data/processed/tier_d_ensemble_rankings.parquet"
merged.to_parquet(out_path, index=False)
print(f"Saved ensemble to {out_path}")

CONFIG_PATH=BASE/"configs/run_config.yaml"
with open(CONFIG_PATH) as f:
    config=yaml.safe_load(f)
held_out=config.get("held_out_test_seasons",[])

feat_path=BASE/"data/processed/features.parquet"
feat=pd.read_parquet(feat_path)
merged_with_actual=pd.merge(
    merged,
    feat[["season_id","award_year","player_name_raw","rank"]],
    on=["season_id","award_year","player_name_raw"],
    how="left"
)

from validation.metrics import evaluate_season

results=[]
for year in held_out:
    sub=merged_with_actual[merged_with_actual["award_year"]==year]
    if sub.empty:
        continue
    actual_df=sub[["player_name_raw","rank"]]
    pred_df=sub[["player_name_raw","final_ensemble_rank"]].rename(columns={"final_ensemble_rank":"predicted_rank"})
    metrics=evaluate_season(actual_df, pred_df)
    metrics["year"]=year
    results.append(metrics)
    print(f"Year {year} Top1 {metrics['top1']} Spearman {metrics['spearman']:.2f}")

if results:
    df_res=pd.DataFrame(results)
    print(f"\nEnsemble Held-out Top1 {df_res['top1'].mean()*100:.1f}% Top3 {df_res['top3'].mean()*100:.1f}% Top5 {df_res['top5'].mean()*100:.1f}% Spearman {df_res['spearman'].mean():.3f}")
