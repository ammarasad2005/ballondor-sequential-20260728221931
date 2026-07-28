"""
Explanation Layer — Per-Candidate Contribution Breakdown
Phase 7 Task 2

For linear model: direct coefficient * feature-value contribution
For GBM: SHAP values (not used since Tier B selected, but placeholder)

Output is part of JSON contract in predict_season.py
"""

import pandas as pd, json, yaml, pickle
from pathlib import Path
import numpy as np

BASE=Path(__file__).parent.parent

def explain_player(player_row, coefficients, scaler, feature_cols):
    """
    Returns explanation dict for a single player
    """
    # Compute contributions as in predict_season.py
    vals=[player_row.get(col,0) for col in feature_cols]
    vals_np=np.array(vals).reshape(1,-1)
    scaled=scaler.transform(vals_np).flatten()
    contributions=[]
    for col, coef, s_val, raw_val in zip(feature_cols, [coefficients.get(c,0) for c in feature_cols], scaled, vals):
        contrib=coef*s_val
        contributions.append({
            "feature":col,
            "coefficient":float(coef),
            "scaled_value":float(s_val),
            "raw_value":float(raw_val) if pd.notna(raw_val) else 0,
            "contribution":float(contrib),
            "abs_contribution":abs(float(contrib))
        })
    # Sort by absolute contribution
    contributions_sorted=sorted(contributions, key=lambda x: x["abs_contribution"], reverse=True)

    # Generate plain language explanation per P5 explicit bias handling
    top3=contributions_sorted[:3]
    explanation_text=f"Player {player_row.get('player_name_raw')} ranked where they do mainly due to: "
    parts=[]
    for c in top3:
        feat=c["feature"]
        contrib=c["contribution"]
        direction="boosted" if contrib>0 else "penalized"
        # Human-readable feature names
        human={
            "goals_percentile_in_year": "goals (peer percentile)",
            "ucl_winner": "Champions League win",
            "league_winner": "domestic league title",
            "nation_won_any_international": "international tournament win with national team",
            "club_prestige_score": "club prestige / big-club bias",
            "signature_moment_flag": "signature moment / recency proxy",
            "is_forward": "being a forward (attacker overrepresentation)",
            "is_defender": "being a defender (positional penalty)",
            "is_goalkeeper": "being a goalkeeper (positional penalty, only 1 winner historically)",
            "is_missing_stats": "missing stats (penalty for gap)",
            "is_world_cup_year": "World Cup year context"
        }
        human_name=human.get(feat, feat)
        parts.append(f"{direction} by {human_name} (contrib {contrib:.2f})")

    explanation_text+=", ".join(parts)

    # Bias transparency per P5
    bias_notes=[]
    if player_row.get("position_group") in ["defender","goalkeeper"]:
        bias_notes.append(f"Predicted rank suppressed partly by positional base rate ({player_row.get('position_group')}) — historically only {5 if player_row.get('position_group')=='defender' else 1} defender/goalkeeper winners per validation report")
    if player_row.get("club_prestige_tier")==3:
        bias_notes.append("Club prestige tier 3 (lower media-market) penalized vs Tier1 big clubs — explicit bias modeling per P5")
    if player_row.get("club_prestige_tier")==1:
        bias_notes.append("Boosted by Tier1 big-club prestige — models documented big-club bias")

    return {
        "player": player_row.get("player_name_raw"),
        "explanation_text": explanation_text,
        "top_contributions": contributions_sorted[:5],
        "all_contributions": contributions_sorted,
        "bias_notes": bias_notes
    }

def explain_season_ranking(rankings_json_path):
    """Load prediction JSON and generate detailed explanations"""
    with open(rankings_json_path) as f:
        data=json.load(f)

    print(f"Explaining season {data['season_id']} with {len(data['rankings'])} players")

    for r in data["rankings"][:5]:
        print(f"\nRank {r['rank']}: {r['player']}")
        for feat in r["top_contributing_features"][:3]:
            print(f"  {feat['feature']}: contrib {feat['contribution']:.3f} (raw {feat.get('raw_value')})")

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--prediction", type=str, required=True, help="Path to prediction JSON")
    args=parser.parse_args()
    explain_season_ranking(args.prediction)
