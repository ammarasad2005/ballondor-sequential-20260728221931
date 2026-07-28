"""
Metrics for validation
- Top-1 accuracy
- Top-3, Top-5 hit rate
- Spearman rho, Kendall tau
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau

def top_k_hit_rate(actual_rank_series, predicted_rank_series, k, winner_only=False):
    """
    For a single season, check if actual winner (rank 1) is within top k predicted
    If winner_only False, could also check top-k overlap? But per spec, top-3/top-5 hit rate is softer version of top-1
    Implementation: actual winner in predicted top k?
    """
    # actual_rank_series: index player, value actual rank
    # predicted_rank_series: index player, value predicted rank (lower is better)
    # Find actual winner player(s)
    actual_winner_idx = actual_rank_series[actual_rank_series==1].index
    if len(actual_winner_idx)==0:
        return np.nan
    # Predicted top k players
    pred_top_k_idx = predicted_rank_series[predicted_rank_series<=k].index
    # Check overlap
    # For winner-only, check if winner in pred top k
    hit = any(idx in pred_top_k_idx for idx in actual_winner_idx)
    return 1 if hit else 0

def spearman_kendall(actual_ranks, predicted_ranks):
    """Compute Spearman rho and Kendall tau between actual and predicted order"""
    # Need to align indices
    # actual_ranks and predicted_ranks are Series indexed by player
    # Drop NaN
    df = pd.DataFrame({"actual": actual_ranks, "pred": predicted_ranks}).dropna()
    if len(df)<2:
        return np.nan, np.nan
    try:
        rho, _ = spearmanr(df["actual"], df["pred"])
    except:
        rho = np.nan
    try:
        tau, _ = kendalltau(df["actual"], df["pred"])
    except:
        tau = np.nan
    return rho, tau

def evaluate_season(actual_df, pred_df, actual_rank_col="rank", pred_rank_col="predicted_rank"):
    """
    actual_df: contains player and actual rank
    pred_df: contains player and predicted rank/score
    Returns dict of metrics for that season
    """
    # Merge on player
    # Assume both have player_name_raw as key
    merged = pd.merge(
        actual_df[["player_name_raw", actual_rank_col]],
        pred_df[["player_name_raw", pred_rank_col]],
        on="player_name_raw",
        how="inner"
    )
    if merged.empty:
        return {"top1": np.nan, "top3": np.nan, "top5": np.nan, "spearman": np.nan, "kendall": np.nan, "n_players":0}

    actual_series = merged.set_index("player_name_raw")[actual_rank_col]
    pred_series = merged.set_index("player_name_raw")[pred_rank_col]

    top1 = top_k_hit_rate(actual_series, pred_series, k=1)
    top3 = top_k_hit_rate(actual_series, pred_series, k=3)
    top5 = top_k_hit_rate(actual_series, pred_series, k=5)
    rho, tau = spearman_kendall(actual_series, pred_series)

    return {
        "top1": top1,
        "top3": top3,
        "top5": top5,
        "spearman": rho,
        "kendall": tau,
        "n_players": len(merged)
    }
