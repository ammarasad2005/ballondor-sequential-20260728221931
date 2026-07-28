"""
Stats Scraper — Wikipedia based
Phase 2 — Individual Performance Data (Modern + Classical)

Attempts to fetch Wikipedia page for each unique player in ground_truth.parquet
and extract:
- Position (infobox)
- Career statistics by club season (appearances, goals)
- Also extracts birth year for canonical ID later

Writes raw to data/raw/stats_modern/ and data/raw/stats_classical/ keyed by player_name_raw,
but also saves combined to data/raw/stats_combined/

Idempotent, checkpointed, with rate limiting and explicit gap logging.

Note: Advanced metrics (xG, xA, progressive, SCA) are not available on Wikipedia;
these will be flagged as missing per Key Focus Area §9. The scraper focuses on
achievable goals/assists/appearances/minutes/position.

For modern era, also attempts to get assists where available (Wikipedia tables often include assists column for recent years? Not consistently).
"""

import requests, pandas as pd, time, json, re, os
from pathlib import Path
from bs4 import BeautifulSoup
import unicodedata

BASE = Path(__file__).parent.parent
RAW_MODERN = BASE / "data" / "raw" / "stats_modern"
RAW_CLASSICAL = BASE / "data" / "raw" / "stats_classical"
RAW_COMBINED = BASE / "data" / "raw" / "stats_combined"
for p in [RAW_MODERN, RAW_CLASSICAL, RAW_COMBINED]:
    p.mkdir(parents=True, exist_ok=True)

PROCESSED_DIR = BASE / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent":"Mozilla/5.0 BallonDor Research Bot 0.1 - academic research"}

GT_PATH = BASE / "data" / "processed" / "ground_truth.parquet"

def normalize_name_for_wiki(name):
    """Try to produce Wikipedia title guess"""
    # Remove footnote markers
    name = re.sub(r'\[.*?\]','',name).strip()
    # Replace spaces with underscores, keep accents for first attempt
    title = name.replace(' ', '_')
    return title

def search_wikipedia_title(query):
    """Use Wikipedia opensearch API to find best title for player"""
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action":"opensearch",
            "search":query,
            "limit":3,
            "namespace":0,
            "format":"json"
        }
        r=requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code==200:
            data=r.json()
            # data[1] is list of titles
            if len(data)>=2 and data[1]:
                return data[1][0]  # first title
    except Exception as e:
        print(f"  search API failed for {query}: {e}")
    return None

def fetch_wikipedia_page(title):
    """Fetch page html by title"""
    # Title may have spaces, use underscores
    url_title = title.replace(' ', '_')
    url = f"https://en.wikipedia.org/wiki/{url_title}"
    try:
        r=requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code==200:
            # Check if page is disambiguation or not footballer
            if "may refer to" in r.text[:2000] and "football" not in r.text[:5000].lower():
                # Disambiguation, need more specific
                return None, url
            return r.text, url
        else:
            return None, url
    except Exception as e:
        print(f"  fetch page {title} error {e}")
        return None, url

def extract_position_and_birth(html):
    """Extract position and birth year from infobox"""
    soup=BeautifulSoup(html, "html.parser")
    # Find infobox
    infobox=soup.find("table", {"class": lambda x: x and "infobox" in x})
    position=None
    birth_year=None
    if infobox:
        # Look for th with Position
        rows=infobox.find_all("tr")
        for row in rows:
            th=row.find("th")
            td=row.find("td")
            if not th or not td:
                continue
            th_text=th.get_text(strip=True).lower()
            if "position" in th_text:
                # td may contain multiple positions, e.g., "Forward", "Midfielder"
                position=td.get_text(separator=" ", strip=True)
                # Clean footnote
                position=re.sub(r'\[.*?\]','',position).strip()
                # Simplify to primary position
                # e.g., "Forward" -> forward, "Attacking midfielder" -> midfielder etc but keep raw
            if "born" in th_text or "date of birth" in th_text:
                # Extract year
                txt=td.get_text()
                m=re.search(r'(\d{4})', txt)
                if m:
                    try:
                        birth_year=int(m.group(1))
                    except:
                        pass
    return position, birth_year

def extract_career_stats_tables(html):
    """Extract career stats tables via pandas.read_html and heuristic"""
    try:
        tables=pd.read_html(html)
    except Exception as e:
        return []
    career_tables=[]
    for idx, df in enumerate(tables):
        # Heuristic: table should have Season or Club and Apps/Goals columns
        cols=[str(c).lower() for c in df.columns]
        # Check for presence of season, club, apps/goals
        has_season=any('season' in c for c in cols)
        has_club=any('club' in c for c in cols)
        has_apps=any('app' in c or 'appearance' in c for c in cols)
        has_goals=any('goal' in c for c in cols)
        # Career stats tables often have multi-level columns
        # For simplicity, if has club and has apps/goals, consider
        if (has_season or has_club) and (has_apps or has_goals):
            # Also check if table contains many rows and looks like stats
            # Save
            career_tables.append((idx, df))
    return career_tables

def parse_career_stats(df):
    """Attempt to parse a career stats DataFrame into structured rows"""
    # Flatten MultiIndex columns if needed
    if isinstance(df.columns, pd.MultiIndex):
        # Join levels
        new_cols=[]
        for col in df.columns:
            # col is tuple
            parts=[str(p).strip() for p in col if str(p).lower()!='nan' and str(p).strip()]
            # Remove empty
            joined=" ".join(parts).strip()
            new_cols.append(joined)
        df.columns=new_cols

    cols_lower=[str(c).lower() for c in df.columns]
    # Identify columns
    season_col=None
    club_col=None
    league_apps_col=None
    league_goals_col=None
    total_apps_col=None
    total_goals_col=None

    for i, c in enumerate(df.columns):
        cl=str(c).lower()
        if 'season' in cl and season_col is None:
            season_col=c
        if 'club' in cl and club_col is None and 'national' not in cl:
            club_col=c
        # League apps/goals often in columns like "League Apps", "League Goals", or "Apps", "Goals"
        # We'll look for exact matches
        if ('apps' in cl or 'appearance' in cl) and ('league' in cl or i==2):
            # Heuristic
            if league_apps_col is None and 'total' not in cl:
                league_apps_col=c
        if 'goal' in cl and ('league' in cl or i==3):
            if league_goals_col is None and 'total' not in cl:
                league_goals_col=c
        # Also check for total
        if ('total' in cl and 'app' in cl) and total_apps_col is None:
            total_apps_col=c
        if ('total' in cl and 'goal' in cl) and total_goals_col is None:
            total_goals_col=c

    # Fallback: if no league specific, use first Apps/Goals columns found
    if league_apps_col is None:
        for c in df.columns:
            if 'app' in str(c).lower():
                league_apps_col=c
                break
    if league_goals_col is None:
        for c in df.columns:
            if 'goal' in str(c).lower():
                league_goals_col=c
                break

    parsed=[]
    for _, row in df.iterrows():
        season=str(row[season_col]) if season_col and season_col in row else None
        club=str(row[club_col]) if club_col and club_col in row else None
        # Clean
        if season:
            season=re.sub(r'\[.*?\]','',season).strip()
        if club:
            club=re.sub(r'\[.*?\]','',club).strip()
        # Apps/goals may be numeric or '--'
        apps=None
        goals=None
        if league_apps_col and league_apps_col in row:
            try:
                val=str(row[league_apps_col]).strip()
                val=re.sub(r'\[.*?\]','',val)
                # Extract number
                m=re.search(r'(\d+)', val)
                if m:
                    apps=int(m.group(1))
            except:
                pass
        if league_goals_col and league_goals_col in row:
            try:
                val=str(row[league_goals_col]).strip()
                val=re.sub(r'\[.*?\]','',val)
                m=re.search(r'(\d+)', val)
                if m:
                    goals=int(m.group(1))
            except:
                pass
        # Only keep if season or club present
        if season or club:
            parsed.append({"season":season, "club":club, "league_apps":apps, "league_goals":goals, "raw":str(row.to_dict())[:500]})
    return parsed

def scrape_player(player_raw):
    """Scrape for a single player raw name"""
    # Check cache
    safe_name=re.sub(r'[^a-zA-Z0-9_\-]', '_', player_raw)[:100]
    combined_file=RAW_COMBINED/f"{safe_name}.json"
    if combined_file.exists():
        try:
            with open(combined_file) as f:
                data=json.load(f)
            if data.get("player_name_raw")==player_raw and data.get("fetch_status")=="ok":
                return data
        except:
            pass

    # Try direct title
    title_guess=normalize_name_for_wiki(player_raw)
    html, url=fetch_wikipedia_page(title_guess)

    # If not found, try search API
    if html is None:
        searched_title=search_wikipedia_title(player_raw)
        if searched_title:
            html, url=fetch_wikipedia_page(searched_title)
            title_guess=searched_title

    # If still not found, try adding "(footballer)" disambiguation
    if html is None:
        for suffix in [" (footballer)", " (footballer, born 1980)", " (Brazilian footballer)", " (Portuguese footballer)"]:
            # Try search with suffix
            attempt=player_raw + suffix
            html, url=fetch_wikipedia_page(attempt.replace(' ','_'))
            if html and "football" in html.lower()[:5000].lower():
                break
            html=None

    # If still not found, log gap
    if html is None:
        result={
            "player_name_raw":player_raw,
            "fetch_status":"not_found",
            "attempted_title":title_guess,
            "url":url if 'url' in locals() else None,
            "position":None,
            "birth_year":None,
            "career_stats":[],
            "error":"page not found or disambiguation"
        }
        # Save to combined
        with open(combined_file,'w') as out:
            json.dump(result, out, indent=2)
        # Also save to classical/modern as gap
        return result

    # Extract position and birth
    position, birth_year=extract_position_and_birth(html)

    # Extract career stats tables
    career_tables=extract_career_stats_tables(html)
    all_stats=[]
    for idx, df in career_tables:
        try:
            parsed=parse_career_stats(df)
            if parsed:
                all_stats.extend(parsed)
        except Exception as e:
            # Log but continue
            pass

    result={
        "player_name_raw":player_raw,
        "fetch_status":"ok",
        "wikipedia_title":title_guess,
        "url":url,
        "position":position,
        "birth_year":birth_year,
        "career_stats_raw_tables_count":len(career_tables),
        "career_stats":all_stats[:200],  # limit
        "html_snippet":html[:2000] if html else None
    }

    # Save to combined
    with open(combined_file,'w') as out:
        json.dump(result, out, indent=2)

    # Also save to era-specific folders based on player appearances? For now save copy to both, but later we will separate by evaluation
    # Actually for idempotency per Architecture Blueprint, we need files keyed by season_id+player_name_raw. But for now we save per player.
    # We'll also create per-season files in a second step.

    time.sleep(1.0)  # rate limit

    return result

def main():
    print("Loading ground truth")
    df=pd.read_parquet(GT_PATH)
    unique_players=df["player_name_raw"].unique().tolist()
    print(f"Unique players to scrape: {len(unique_players)}")

    # Sort for deterministic order
    unique_players=sorted(unique_players)

    # Stats file for overall
    stats_summary=[]
    gaps=[]

    for i, player in enumerate(unique_players):
        print(f"[{i+1}/{len(unique_players)}] Scraping {player}")
        result=scrape_player(player)
        stats_summary.append({
            "player_name_raw":player,
            "status":result.get("fetch_status"),
            "position":result.get("position"),
            "birth_year":result.get("birth_year"),
            "career_stats_count":len(result.get("career_stats",[])),
            "url":result.get("url")
        })
        if result.get("fetch_status")!="ok":
            gaps.append(player)

    # Save summary
    summary_df=pd.DataFrame(stats_summary)
    summary_df.to_csv(RAW_COMBINED/"scrape_summary.csv", index=False)
    summary_df.to_parquet(PROCESSED_DIR/"stats_scrape_summary.parquet", index=False)
    print(f"Finished. Total {len(stats_summary)}, gaps {len(gaps)}")
    if gaps:
        print(f"Gaps sample: {gaps[:20]}")
        with open(RAW_COMBINED/"gaps.json",'w') as f:
            json.dump(gaps, f, indent=2)

    # Also produce per-ground-truth-row raw files keyed by season+player for checkpoint requirement
    # Create directory structure data/raw/stats_modern/{season_id}_{player}.json etc
    print("Creating per-season checkpoint files...")
    for _, row in df.iterrows():
        season_id=row["season_id"]
        player=row["player_name_raw"]
        safe_player=re.sub(r'[^a-zA-Z0-9_\-]', '_', player)[:80]
        # Determine era
        award_year=int(row["award_year"])
        if award_year >= 2014:
            target_dir=RAW_MODERN
        else:
            target_dir=RAW_CLASSICAL
        src_file=RAW_COMBINED/f"{re.sub(r'[^a-zA-Z0-9_\\-]', '_', player)[:100]}.json"
        dest_file=target_dir/f"{season_id}_{safe_player}.json"
        if src_file.exists():
            # Copy or link content
            try:
                with open(src_file) as sf:
                    data=json.load(sf)
                # Add season context
                data["season_id"]=season_id
                data["award_year"]=award_year
                with open(dest_file,'w') as df_out:
                    json.dump(data, df_out, indent=2)
            except Exception as e:
                # If copy fails, create minimal gap file
                with open(dest_file,'w') as df_out:
                    json.dump({"season_id":season_id, "player_name_raw":player, "error":str(e)}, df_out)
        else:
            with open(dest_file,'w') as df_out:
                json.dump({"season_id":season_id, "player_name_raw":player, "error":"no source file, gap"}, df_out)

    print("Per-season checkpoints created")

if __name__=="__main__":
    main()
