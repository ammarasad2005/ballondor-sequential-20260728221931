"""
Modern Advanced Metrics Scraper — Understat
Phase 2 Improvement: FBRef was blocked by Cloudflare, but Understat provides xG, xA, xGChain, etc. via
https://understat.com/getLeagueData/<league>/<season> endpoint which is accessible via simple requests
with Referer header (no Cloudflare challenge)

Scrapes for leagues: EPL, La_liga, Bundesliga, Serie_A, Ligue_1
Seasons: 2014-2024 (Understat season 2014 = 2014/15, which maps to Ballon d'Or award year 2015 as season ending in 2015, but we use mapping award_year -> Understat season = award_year-1)

Saves raw to data/raw/stats_modern/understat/
And per-player advanced to data/raw/stats_modern/advanced/

Idempotent, checkpointed
"""

import requests, json, time
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz, process

BASE=Path(__file__).parent.parent
RAW_UNDERSTAT=BASE/"data/raw/stats_modern/understat"
RAW_ADV=BASE/"data/raw/stats_modern/advanced"
for p in [RAW_UNDERSTAT, RAW_ADV]:
    p.mkdir(parents=True, exist_ok=True)

GT_PATH=BASE/"data/processed/ground_truth.parquet"
FEAT_PATH=BASE/"data/processed/features.parquet"

HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":"https://understat.com/league/EPL/2023",
    "X-Requested-With":"XMLHttpRequest"
}

LEAGUES=["EPL","La_liga","Bundesliga","Serie_A","Ligue_1"]
SEASONS=list(range(2014, 2025))  # 2014=2014/15 up to 2024=2024/25

def fetch_league_season(league, season, force=False):
    """Fetch Understat league data for given league and season"""
    filename=RAW_UNDERSTAT/f"{league}_{season}.json"
    if filename.exists() and not force:
        try:
            with open(filename) as f:
                data=json.load(f)
            if data.get("players"):
                print(f"[{league} {season}] Skipping, cached {len(data['players'])} players")
                return data
        except:
            pass

    url=f"https://understat.com/getLeagueData/{league}/{season}"
    # Update Referer to match league/season
    headers=HEADERS.copy()
    headers["Referer"]=f"https://understat.com/league/{league}/{season}"
    print(f"[{league} {season}] Fetching {url}")
    try:
        r=requests.get(url, headers=headers, timeout=20)
        if r.status_code!=200:
            print(f"  Failed {r.status_code}")
            return None
        data=r.json()
        # Save raw
        with open(filename,'w') as out:
            json.dump(data, out)
        print(f"  Saved {len(data.get('players',[]))} players")
        time.sleep(1.5)
        return data
    except Exception as e:
        print(f"  Error {e}")
        return None

def main():
    # First, fetch all league/season data
    all_players_data={}  # key (league, season) -> players list
    for league in LEAGUES:
        for season in SEASONS:
            data=fetch_league_season(league, season)
            if data:
                all_players_data[(league, season)]=data.get("players",[])

    # Now, for each modern ground truth row (award_year>=2014), try to find matching Understat player
    gt=pd.read_parquet(GT_PATH)
    modern_gt=gt[gt["award_year"]>=2014].copy()
    print(f"\nModern ground truth rows: {len(modern_gt)}, unique players {modern_gt['player_name_raw'].nunique()}")

    # For mapping, we need award_year -> Understat season = award_year-1
    # e.g., Ballon d'Or 2015 -> Understat season 2014 (2014/15)
    # For season-based 2022+, Ballon d'Or 2022 -> Understat season 2021 (2021/22) which is award_year-1 as well, so same mapping

    matched=0
    unmatched=[]
    for idx, row in modern_gt.iterrows():
        award_year=int(row["award_year"])
        understat_season=award_year-1
        player_raw=row["player_name_raw"]
        # Search across all leagues for that understat_season for matching player name
        found=None
        best_score=0
        best_league=None
        for league in LEAGUES:
            key=(league, understat_season)
            players=all_players_data.get(key,[])
            if not players:
                continue
            # Use rapidfuzz to find best match
            # Extract player names list
            names=[p.get("player_name","") for p in players]
            if not names:
                continue
            # Exact match first
            if player_raw in names:
                found=next(p for p in players if p.get("player_name")==player_raw)
                best_score=100
                best_league=league
                break
            # Fuzzy
            result=process.extractOne(player_raw, names, scorer=fuzz.token_sort_ratio)
            if result:
                best_match, score, _ = result
                if score>best_score:
                    best_score=score
                    # Find player dict
                    for p in players:
                        if p.get("player_name")==best_match:
                            found=p
                            best_league=league
                            break
        # Threshold for fuzzy match: 80?
        if found and best_score>=80:
            # Save advanced stats
            safe_name=player_raw.replace(" ","_").replace("/","_")[:80]
            # Sanitize
            import re
            safe_name=re.sub(r'[^a-zA-Z0-9_\-]', '_', safe_name)
            season_id=row["season_id"]
            out_file=RAW_ADV/f"{season_id}_{safe_name}_understat.json"
            output={
                "season_id":season_id,
                "award_year":award_year,
                "understat_season":understat_season,
                "player_name_raw":player_raw,
                "matched_name":found.get("player_name"),
                "match_score":best_score,
                "matched_league":best_league,
                "team_title":found.get("team_title"),
                "games":found.get("games"),
                "time":found.get("time"),
                "goals":found.get("goals"),
                "xG":found.get("xG"),
                "assists":found.get("assists"),
                "xA":found.get("xA"),
                "shots":found.get("shots"),
                "key_passes":found.get("key_passes"),
                "xGChain":found.get("xGChain"),
                "xGBuildup":found.get("xGBuildup"),
                "npg":found.get("npg"),
                "npxG":found.get("npxG"),
                "position":found.get("position"),
                "source":f"https://understat.com/getLeagueData/{best_league}/{understat_season}",
                "raw":found
            }
            with open(out_file,'w') as out:
                json.dump(output, out, indent=2)
            matched+=1
        else:
            unmatched.append((award_year, player_raw, best_score, found.get("player_name") if found else None))

    print(f"\nMatched {matched}/{len(modern_gt)} modern rows ({matched/len(modern_gt)*100:.1f}%)")
    print(f"Unmatched {len(unmatched)} sample: {unmatched[:20]}")

    # Save summary
    summary_path=BASE/"data/processed/understat_match_summary.json"
    with open(summary_path,'w') as f:
        json.dump({
            "matched":matched,
            "total":len(modern_gt),
            "match_rate":matched/len(modern_gt) if len(modern_gt) else 0,
            "unmatched_sample":unmatched[:100]
        }, f, indent=2)

    print(f"Saved summary to {summary_path}")

if __name__=="__main__":
    main()
