"""
Web Layer for Testing — BallonIQ
Thin API wrapping Stage 6 JSON contract per WEB_LAYER_HANDOFF.md
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import pandas as pd
import json
from inference.predict_season import predict_season
import yaml

BASE=Path(__file__).parent
app=FastAPI(title="BallonIQ - Ballon d'Or Prediction Engine", description="Learning-to-rank system modeling jury decisions 1956-present", version="0.1")

# Load features to get available seasons
FEAT_PATH=BASE/"data/processed/features.parquet"
try:
    df=pd.read_parquet(FEAT_PATH)
    available_seasons=sorted(df['season_id'].unique().tolist())
except:
    available_seasons=[]

@app.get("/")
async def root():
    html="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>BallonIQ — Ballon d'Or Prediction Engine</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h1 { color: #333; }
            .season-browser { margin: 20px 0; }
            .ranking-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            .ranking-table th, .ranking-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            .ranking-table th { background: #f2f2f2; }
            .explanation { background: #eef; padding: 10px; border-radius: 5px; margin: 10px 0; }
            .bias-note { background: #ffe; padding: 5px; border-left: 3px solid #fa0; margin: 5px 0; }
            select, button { padding: 8px 12px; font-size: 14px; }
            .scenario { background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }
            .slider { width: 200px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>BallonIQ — Ballon d'Or Prediction Engine</h1>
            <p>Learning-to-rank system modeling jury decisions 1956-present with 2004 nominees, 78 features (xG/xA via Understat), Tier B linear ranker selected (50% held-out Top1, 66.7% Top3, Spearman 0.53)</p>
            
            <div class="season-browser">
                <h3>Season Browser</h3>
                <label>Select Season: </label>
                <select id="seasonSelect">
                    <option value="">-- Choose --</option>
                </select>
                <button onclick="loadSeason()">Load Ranking</button>
            </div>

            <div id="rankingDiv"></div>
            <div id="explanationDiv"></div>

            <div class="scenario">
                <h3>Scenario Tool (What-If) — Test Jury Factors</h3>
                <p>Manually vary a player's metrics and see rank shift live (per WEB_LAYER_HANDOFF.md interaction model)</p>
                <label>Player: <select id="playerSelect"></select></label><br><br>
                <label>Goals Percentile: <input type="range" id="goalsSlider" min="0" max="100" value="50" class="slider" oninput="document.getElementById('goalsVal').innerText=this.value"> <span id="goalsVal">50</span></label><br>
                <label>UCL Winner: <select id="uclSelect"><option value="0">No</option><option value="1">Yes</option></select></label><br>
                <label>Nation Won International: <select id="nationSelect"><option value="0">No</option><option value="1">Yes</option></select></label><br>
                <label>Club Prestige (1-3): <input type="range" id="prestigeSlider" min="1" max="3" value="2" class="slider" oninput="document.getElementById('prestigeVal').innerText=this.value"> <span id="prestigeVal">2</span></label><br><br>
                <button onclick="runScenario()">Run Scenario</button>
                <div id="scenarioResult"></div>
            </div>
        </div>

        <script>
            let currentData=null;
            // Load available seasons
            fetch('/api/seasons')
                .then(r=>r.json())
                .then(data=>{
                    const select=document.getElementById('seasonSelect');
                    data.seasons.forEach(s=>{
                        const opt=document.createElement('option');
                        opt.value=s;
                        opt.textContent=s;
                        select.appendChild(opt);
                    });
                    // Default to most recent
                    if(data.seasons.length>0){
                        select.value=data.seasons[data.seasons.length-1];
                    }
                });

            function loadSeason(){
                const season=document.getElementById('seasonSelect').value;
                if(!season) return;
                fetch(`/api/predict?season=${season}`)
                    .then(r=>r.json())
                    .then(data=>{
                        currentData=data;
                        displayRanking(data);
                    });
            }

            function displayRanking(data){
                const div=document.getElementById('rankingDiv');
                let html=`<h3>Predicted Ranking for ${data.season_id} (Model: ${data.model_version})</h3>`;
                html+=`<p>Generated: ${data.generated_at}</p>`;
                html+=`<table class="ranking-table"><tr><th>Rank</th><th>Player</th><th>Club</th><th>Nation</th><th>Position</th><th>Score</th><th>Actual Rank</th></tr>`;
                data.rankings.slice(0,15).forEach(r=>{
                    html+=`<tr><td>${r.rank}</td><td>${r.player}</td><td>${r.club}</td><td>${r.nation}</td><td>${r.position}</td><td>${r.score.toFixed(3)}</td><td>${r.actual_rank || ''}</td></tr>`;
                });
                html+=`</table>`;
                div.innerHTML=html;

                // Populate player select for scenario
                const playerSelect=document.getElementById('playerSelect');
                playerSelect.innerHTML='';
                data.rankings.forEach(r=>{
                    const opt=document.createElement('option');
                    opt.value=r.player;
                    opt.textContent=`${r.rank}. ${r.player} (${r.club})`;
                    playerSelect.appendChild(opt);
                });

                // Show explanation for top 1
                if(data.rankings.length>0){
                    showExplanation(data.rankings[0]);
                }
            }

            function showExplanation(playerData){
                const div=document.getElementById('explanationDiv');
                let html=`<h3>Why ${playerData.player} ranks #${playerData.rank}?</h3>`;
                html+=`<div class="explanation">`;
                playerData.top_contributing_features.forEach(f=>{
                    const direction=f.contribution>0?'boosted':'penalized';
                    html+=`<div>${direction} by <b>${f.feature}</b>: ${f.contribution.toFixed(3)} (raw ${f.raw_value})</div>`;
                });
                html+=`</div>`;
                div.innerHTML=html;
            }

            function runScenario(){
                if(!currentData) return alert('Load a season first');
                const player=document.getElementById('playerSelect').value;
                const goals=document.getElementById('goalsSlider').value;
                const ucl=document.getElementById('uclSelect').value;
                const nation=document.getElementById('nationSelect').value;
                const prestige=document.getElementById('prestigeSlider').value;

                fetch('/api/scenario', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({
                        season_id: currentData.season_id,
                        player: player,
                        modified_features: {
                            goals_percentile_in_year: parseFloat(goals),
                            ucl_winner: parseInt(ucl),
                            nation_won_any_international: parseInt(nation),
                            club_prestige_score: parseInt(prestige)
                        }
                    })
                })
                .then(r=>r.json())
                .then(data=>{
                    const div=document.getElementById('scenarioResult');
                    let html=`<h4>Scenario Result for ${player}</h4>`;
                    html+=`<p>New score: ${data.new_score.toFixed(3)}, New rank: ${data.new_rank} (was ${data.old_rank})</p>`;
                    html+=`<p>${data.explanation}</p>`;
                    div.innerHTML=html;
                });
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/api/seasons")
async def get_seasons():
    return {"seasons": available_seasons, "count": len(available_seasons), "held_out": [2018,2019,2021,2022,2023,2024]}

@app.get("/api/predict")
async def api_predict(season: str = Query(..., description="Season ID e.g., 2024")):
    try:
        output=predict_season(season)
        if output is None:
            raise HTTPException(status_code=404, detail=f"Season {season} not found")
        return JSONResponse(content=output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scenario")
async def api_scenario(payload: dict):
    """
    Scenario tool: manually vary a player's metrics and see rank shift
    Payload: {season_id, player, modified_features: {goals_percentile_in_year, ucl_winner, ...}}
    """
    try:
        season_id=payload.get("season_id")
        player_name=payload.get("player")
        modified=payload.get("modified_features",{})

        # Load original prediction to get baseline
        original=predict_season(season_id)
        if not original:
            raise HTTPException(status_code=404, detail="Season not found")

        # Find player in original rankings
        player_data=None
        for r in original["rankings"]:
            if r["player"]==player_name:
                player_data=r
                break
        if not player_data:
            raise HTTPException(status_code=404, detail="Player not found in season")

        old_rank=player_data["rank"]
        old_score=player_data["score"]

        # For scenario, we need to recompute score with modified features
        # Simplified: we approximate new score by adjusting old score based on feature changes
        # In real implementation, we would reload features.parquet, modify the row, re-scale, recompute w·features
        # Here we implement simplified logic using same model as predict_season

        import pandas as pd
        from pathlib import Path
        import pickle, json
        BASE=Path(__file__).parent
        FEAT_PATH=BASE/"data/processed/features.parquet"
        MODEL_PATH=BASE/"models/tier_b_model.pkl"
        SCALER_PATH=BASE/"models/tier_b_scaler.pkl"
        FEATURES_USED_PATH=BASE/"data/processed/tier_b_features_used.json"

        df=pd.read_parquet(FEAT_PATH)
        sub=df[df["season_id"]==str(season_id)].copy()
        if sub.empty:
            sub=df[df["award_year"]==int(season_id)].copy()

        with open(FEATURES_USED_PATH) as f:
            feat_info=json.load(f)
        feature_cols=feat_info["features"]

        with open(MODEL_PATH,'rb') as f:
            model=pickle.load(f)
        with open(SCALER_PATH,'rb') as f:
            scaler=pickle.load(f)

        # Find player row in features
        player_row=sub[sub["player_name_raw"]==player_name]
        if player_row.empty:
            raise HTTPException(status_code=404, detail="Player not in features")

        # Apply modifications
        import numpy as np
        # For each modified feature, update the row
        for feat, val in modified.items():
            if feat in player_row.columns:
                player_row.loc[player_row.index[0], feat]=val
            # Special handling for prestige scaled
            if feat=="club_prestige_score":
                # Also need to handle scaled version later
                pass

        # Impute missing
        for col in feature_cols:
            if col in player_row.columns:
                median=df[col].median()
                player_row[col]=player_row[col].fillna(median if pd.notna(median) else 0)
            else:
                player_row[col]=0

        X=player_row[feature_cols].values
        X_scaled=scaler.transform(X)
        new_score=float(np.dot(X_scaled, model.coef_.T).flatten()[0])

        # To compute new rank, we need scores for all other players in season
        # Compute scores for all players in season with original features
        all_scores=[]
        for idx, row in sub.iterrows():
            # For the modified player, use modified row
            if row["player_name_raw"]==player_name:
                # Use modified and scaled
                all_scores.append((row["player_name_raw"], new_score))
            else:
                # Compute original score for other players
                # Use same model
                # Get features for this row
                # Impute
                feat_vals=[]
                for col in feature_cols:
                    val=row.get(col,0)
                    if pd.isna(val):
                        median=df[col].median()
                        val=median if not pd.isna(median) else 0
                    feat_vals.append(val)
                feat_vals_np=np.array(feat_vals).reshape(1,-1)
                feat_scaled=scaler.transform(feat_vals_np)
                s=float(np.dot(feat_scaled, model.coef_.T).flatten()[0])
                all_scores.append((row["player_name_raw"], s))

        # Rank by score descending
        all_scores_sorted=sorted(all_scores, key=lambda x: x[1], reverse=True)
        new_rank=None
        for rank, (pname, sc) in enumerate(all_scores_sorted, start=1):
            if pname==player_name:
                new_rank=rank
                break

        explanation=f"Changing {list(modified.keys())} from original to {modified} changes score from {old_score:.3f} to {new_score:.3f}, rank from {old_rank} to {new_rank}. This demonstrates how jury factors (e.g., increasing goals percentile or adding UCL win) boosts rank."

        return {
            "season_id": season_id,
            "player": player_name,
            "old_rank": old_rank,
            "old_score": old_score,
            "new_rank": new_rank,
            "new_score": new_score,
            "modified_features": modified,
            "explanation": explanation
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# For testing, run with uvicorn
if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
