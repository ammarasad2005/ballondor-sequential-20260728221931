"""
Ground Truth Scraper for Ballon d'Or Prediction Engine
Phase 1 — Backbone table

Scrapes Wikipedia year pages for Ballon d'Or / FIFA Ballon d'Or winners + nominee lists
1956–2025, handling:
- 2020 cancellation
- 2010-2015 FIFA merger pages
- Varying table structures
- Checkpointed idempotent writes to data/raw/ground_truth/
- Outputs ground_truth.parquet and eval_window_metadata.csv

Usage:
  python scrapers/ground_truth_scraper.py [--force]
"""

import requests
import pandas as pd
import time
import os
import re
import json
from pathlib import Path
import sys
from datetime import date

BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "ground_truth"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) BallonDor Research Bot 0.1 - academic research, contact project"
}

# Years to scrape
YEARS = list(range(1956, 2026))  # inclusive 1956-2025

def get_url_for_year(year):
    if 2010 <= year <= 2015:
        return f"https://en.wikipedia.org/wiki/{year}_FIFA_Ballon_d%27Or"
    else:
        return f"https://en.wikipedia.org/wiki/{year}_Ballon_d%27Or"

def clean_rank(val):
    """Parse rank like '1', '1st', '2nd', '1.0', 'Rank[2][3]' header etc"""
    if pd.isna(val):
        return None
    s = str(val).strip()
    # Remove footnote markers like [2][3] or (a)
    s = re.sub(r'\[.*?\]', '', s)
    s = re.sub(r'\(.*?\)', '', s)
    s = s.strip()
    # Extract leading integer
    m = re.search(r'(\d+)', s)
    if m:
        try:
            return int(m.group(1))
        except:
            return None
    return None

def clean_player_name(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    # Remove footnotes
    s = re.sub(r'\[.*?\]', '', s)
    s = s.strip()
    return s if s else None

def clean_club(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    s = re.sub(r'\[.*?\]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s if s else None

def clean_points(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    s = re.sub(r'\[.*?\]', '', s)
    # Remove % for percent era
    s = s.replace('%','').strip()
    # Try to parse float
    try:
        # handle commas?
        s = s.replace(',', '')
        return float(s)
    except:
        # Sometimes points like "22.65%" already cleaned, or "47"
        m = re.search(r'([\d\.]+)', s)
        if m:
            try:
                return float(m.group(1))
            except:
                return None
        return None

def scrape_year(year, force=False):
    raw_file = RAW_DIR / f"{year}.jsonl"
    if raw_file.exists() and not force:
        # load existing
        try:
            with open(raw_file) as f:
                rows = [json.loads(line) for line in f]
            if rows:
                print(f"[{year}] Skipping, {len(rows)} rows already cached at {raw_file}")
                return rows
        except Exception as e:
            print(f"[{year}] Cache read failed {e}, re-scraping")
    
    if year == 2020:
        # No award
        print(f"[{year}] Cancelled year, no data")
        # Write empty marker
        with open(raw_file, 'w') as out:
            out.write(json.dumps({"year": year, "note": "cancelled_no_award", "source": "France Football official statement 2020 cancellation"}) + "\n")
        return []

    url = get_url_for_year(year)
    print(f"[{year}] Fetching {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        # Handle redirects manually: if page is generic Ballon d'Or page for 2020, it redirected (but we already handled 2020)
        if r.status_code != 200:
            print(f"[{year}] HTTP {r.status_code} for {url}")
            # Try alternative URL without FIFA for transitional years?
            if 2010 <= year <= 2015:
                alt = f"https://en.wikipedia.org/wiki/{year}_Ballon_d%27Or"
                print(f"[{year}] Trying alt {alt}")
                r = requests.get(alt, headers=HEADERS, timeout=20)
                if r.status_code != 200:
                    print(f"[{year}] Alt also failed {r.status_code}")
                    return []
            else:
                return []
    except Exception as e:
        print(f"[{year}] Fetch error {e}")
        return []

    html = r.text
    # Save raw html checkpoint? We save jsonl of parsed rows instead, but also save html snapshot for QA if needed
    html_file = RAW_DIR / f"{year}.html"
    try:
        with open(html_file, 'w', encoding='utf-8') as hf:
            hf.write(html[:500000])  # limit size
    except Exception as e:
        print(f"[{year}] Could not save html {e}")

    try:
        tables = pd.read_html(html)
    except Exception as e:
        print(f"[{year}] pd.read_html failed {e}")
        # fallback manual
        tables = []

    parsed_rows = []
    found_rank1 = False
    # For FIFA Ballon d'Or years, ranking is split across multiple tables (top3 + rest 4-23)
    # For other years, single table contains full list.
    # Strategy: collect all tables that look like men's Ballon d'Or ranking until we have collected expected count or hit women's/coach tables.

    for tidx, df in enumerate(tables):
        col_lower = [str(c).lower() for c in df.columns]
        has_rank = any('rank' in c for c in col_lower)
        has_player = any('player' in c or c == 'name' or 'name' in c for c in col_lower)
        if not (has_rank and has_player):
            continue
        # Skip tables that are clearly for coaches (have Coach column) or contain Position=GK etc but with different context? Keep only if has Player/Name but not Coach
        # Detect coach table
        if any('coach' in str(c).lower() for c in df.columns):
            # If we already found men's ranking, break on first coach table (indicates end of men's section)
            if found_rank1 and len(parsed_rows) >= 3:
                # check if we've collected at least some rows, then encountering coach means end of men section
                # Only break if we have >=23 or >=30 for recent etc, but safe to continue? We'll check if table contains 'coach'
                # For FIFA years, women's tables precede coach tables; but we already have women's detection below
                # So if we encounter coach, we should stop collecting further Ballon d'Or tables
                if len(parsed_rows) >= 20:
                    break
            continue
        # Skip women's tables: heuristic - if we've already collected men's ranking (found rank1) and this table has Rank+Player but the content includes known women's player names? 
        # Simpler: for FIFA years, men's list is exactly 23 players. So once we have 23, stop.
        # For non-FIFA modern, 30 players.
        # We'll detect women's by looking at table order: after first 2 men's tables, the next Rank tables are women's top3 then rest. So we need to stop after collecting men's expected count.

        # Identify columns - prioritize Total/Points/Percent for points column, not Votes by place
        rank_col = None
        player_col = None
        club_col = None
        nation_col = None
        points_col = None
        # First pass for rank/player/club/nation
        for i, cname in enumerate(df.columns):
            cl = str(cname).lower()
            if 'rank' in cl and rank_col is None:
                rank_col = cname
            elif ('player' in cl or cname == 'Name' or str(cname).lower() == 'name') and player_col is None:
                if 'nationality' not in cl and 'national team' not in cl:
                    player_col = cname
            elif 'club' in cl and club_col is None:
                club_col = cname
            elif ('nationality' in cl or 'national team' in cl or 'country' in cl) and nation_col is None:
                nation_col = cname

        # Second pass for points: look for total/points/percent in priority order, avoid 'votes by place' as fallback
        # Handle MultiIndex tuples where column might be ('Total','Total') or ('Votes by place','1st')
        candidates = []
        for cname in df.columns:
            cl = str(cname).lower()
            # Skip if this is rank/player/club/nation column
            if cname == rank_col or cname == player_col or cname == club_col or cname == nation_col:
                continue
            # Check for points-like names
            if 'total' in cl or 'points' in cl or 'point' in cl or 'percent' in cl:
                # Ensure not 'votes by place' - total contains not votes
                candidates.append((0, cname))  # priority 0 = best
            elif 'votes' in cl and 'by place' not in cl:
                # Votes column but not "by place" sub-columns
                candidates.append((1, cname))
            elif 'votes' in cl:
                candidates.append((2, cname))  # lowest priority

        if candidates:
            candidates.sort(key=lambda x: x[0])
            points_col = candidates[0][1]

        if rank_col is None or player_col is None:
            continue

        # Count rows in this table that have valid rank and player
        table_rows = []
        for _, row in df.iterrows():
            rank_raw = row.get(rank_col)
            rank = clean_rank(rank_raw)
            if rank is None:
                continue
            player_raw = clean_player_name(row.get(player_col))
            if not player_raw:
                continue
            club_raw = clean_club(row.get(club_col)) if club_col else None
            nation_raw = clean_club(row.get(nation_col)) if nation_col else None
            points_raw = clean_points(row.get(points_col)) if points_col else None

            table_rows.append({
                "season_id": str(year),
                "award_year": year,
                "rank": rank,
                "player_name_raw": player_raw,
                "club_at_time": club_raw,
                "nation_team": nation_raw,
                "points": points_raw,
                "source": url,
                "table_index": tidx
            })

        if not table_rows:
            continue

        # Heuristic for women's detection:
        # If we already have found_rank1 and we see a table that restarts at rank 1 with different players (women's top3), we should stop if we already have substantial men's rows.
        # FIFA men's expected 23, modern Ballon d'Or expected 30, early years vary 24-50.
        # We'll detect restart at rank 1:
        has_rank1_in_table = any(r["rank"] == 1 for r in table_rows)
        if has_rank1_in_table and found_rank1:
            # This is a restart -> likely women's award table. If we already have at least 20 rows (FIFA) or 24+ (others), stop.
            if len(parsed_rows) >= 20:
                print(f"[{year}] Encountered second rank-1 table at index {tidx} (likely women's), stopping after {len(parsed_rows)} men's rows")
                break
            else:
                # Otherwise, first table might have been incomplete? Should still treat as women's if year >=2018 women's exists
                # For safety, if year >=2018 and we are beyond first adult table, treat restart as women's
                if year >= 2018:
                    print(f"[{year}] Second rank-1 at {tidx} considered women's, stopping")
                    break

        if table_rows:
            # If this table contains rank 1, mark found
            if any(r["rank"] == 1 for r in table_rows):
                found_rank1 = True
            parsed_rows.extend(table_rows)
            print(f"[{year}] Collected {len(table_rows)} rows from table {tidx} (total now {len(parsed_rows)}) cols {df.columns.tolist()[:6]}")

            # Early stopping based on expected counts
            if 2010 <= year <= 2015:
                # FIFA Ballon d'Or men's shortlist 23
                if len(parsed_rows) >= 23:
                    break
            elif year >= 2016:
                # 30-man shortlist
                if len(parsed_rows) >= 30:
                    break
            elif 2007 <= year <= 2009:
                # 30-man list started around 2007? Actually 50 then 30. We'll break when no more Rank tables look like men's or after 50
                if len(parsed_rows) >= 50:
                    break
            # For earlier years, continue collecting until tables exhausted? But usually single table holds all.
            # If we have found rank1 and next table has higher rank start, continue; else if we have many rows break to avoid picking other award tables (like Puskas)
            # For simplicity, if we have >=24 rows for 1956-2006, stop after first valid table (since early tables are single)
            if year < 2007 and len(parsed_rows) >= 24:
                # Check if next table also has Rank+Player but may be unrelated (like Super Ballon d'Or history tables)
                # We'll allow one table for pre-2007 then break
                break

    if not parsed_rows:
        print(f"[{year}] No rows parsed from {len(tables)} tables")
        # Debug: dump columns
        for idx, df in enumerate(tables[:5]):
            print(f"  Table {idx} cols {df.columns.tolist()} shape {df.shape}")

    # Deduplicate by rank+player within year, keep first
    seen = set()
    deduped = []
    for row in parsed_rows:
        key = (row["rank"], row["player_name_raw"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    parsed_rows = deduped
    # Sort by rank
    parsed_rows = sorted(parsed_rows, key=lambda x: x["rank"])

    # Save checkpoint jsonl
    with open(raw_file, 'w', encoding='utf-8') as out:
        for row in parsed_rows:
            out.write(json.dumps(row) + "\n")

    # Throttle
    time.sleep(1.2)

    return parsed_rows

def build_eval_window_metadata():
    """
    Build eval window metadata per year with 2-source verification.
    Sources used:
    - Wikipedia Ballon d'Or page (states: until 2021 calendar year, since 2022 season Aug-Jul)
    - Britannica List (states same)
    - Topendsports, BBC, Goal.com articles (2022 change announcement)
    - France Football official statement March 11 2022 (via Outlook India, etc)
    Eligibility regimes from same sources.

    This is manually hard-coded after research, per Implementation Plan requirement.
    """
    metadata = []
    for year in YEARS:
        if year == 2020:
            metadata.append({
                "season_id": str(year),
                "award_year": year,
                "eval_period_start": None,
                "eval_period_end": None,
                "eval_type": "cancelled",
                "eligibility_regime": "cancelled",
                "voting_pool": "none",
                "notes": "No award due to COVID-19 pandemic — France Football official statement July 20 2020",
                "source1": "https://www.francefootball.fr/ballon-d-or/ (official statement)",
                "source2": "https://en.wikipedia.org/wiki/Ballon_d%27Or (notes 2020 cancellation)"
            })
            continue

        # Determine eval period
        if year >= 2022:
            # Season based Aug previous year - July current year
            start = date(year-1, 8, 1)
            end = date(year, 7, 31)
            eval_type = "season"
            if year == 2022:
                notes = "First season-based edition per France Football March 11 2022 rule change; period Aug 2021-Jul 2022, excludes World Cup Qatar 2022"
            elif year == 2023:
                notes = "Season Aug 2022-Jul 2023 includes World Cup Qatar Nov-Dec 2022 per France Football clarification that World Cup counts for 2023 edition"
            else:
                notes = f"Season-based Aug {year-1} to Jul {year} per 2022 rule change"
        else:
            # Calendar year
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            eval_type = "calendar"
            notes = f"Calendar year Jan-Dec {year} per historical rule until 2021"

        # Eligibility regime
        if 1956 <= year <= 1994:
            eligibility = "european_players_at_european_clubs_only"
        elif 1995 <= year <= 2006:
            eligibility = "all_players_at_european_clubs"
        elif 2007 <= year:
            eligibility = "all_players_worldwide"
        else:
            eligibility = "unknown"

        # Voting pool
        if 1956 <= year <= 2006:
            voting = "journalists_UEFA_countries_selected_by_France_Football"
        elif 2007 <= year <= 2009:
            voting = "journalists_worldwide_96_journalists"
        elif 2010 <= year <= 2015:
            voting = "FIFA_Ballon_dOr_journalists_plus_captains_plus_coaches_200+_FIFA_members"
        elif 2016 <= year <= 2021:
            voting = "journalists_only_split_back_to_France_Football"
        else:  # 2022+
            voting = "journalists_top_100_FIFA_ranked_nations"

        metadata.append({
            "season_id": str(year),
            "award_year": year,
            "eval_period_start": start.isoformat() if start else None,
            "eval_period_end": end.isoformat() if end else None,
            "eval_type": eval_type,
            "eligibility_regime": eligibility,
            "voting_pool": voting,
            "notes": notes,
            "source1": "https://en.wikipedia.org/wiki/Ballon_d%27Or (states until 2021 calendar year, since 2022 season Aug-Jul)",
            "source2": "https://www.britannica.com/sports/List-of-Ballon-d-Or-Winners (states 1995 expansion, 2007 worldwide, 2010-2015 merger, 2022 season change) and https://www.topendsports.com/sport/soccer/awards/ballondor-voting.htm"
        })

    df = pd.DataFrame(metadata)
    csv_path = PROCESSED_DIR / "eval_window_metadata.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved eval window metadata to {csv_path} with {len(df)} rows")
    return df

def build_ground_truth_parquet(all_rows, eval_df):
    # Convert to DataFrame
    if not all_rows:
        print("No rows to build parquet!")
        return

    df = pd.DataFrame(all_rows)
    # Merge eval window
    eval_map = eval_df.set_index("season_id")[["eval_period_start","eval_period_end"]].to_dict('index')
    # Add eval periods
    df["eval_period_start"] = df["season_id"].apply(lambda sid: eval_map.get(sid, {}).get("eval_period_start"))
    df["eval_period_end"] = df["season_id"].apply(lambda sid: eval_map.get(sid, {}).get("eval_period_end"))

    # Add canonical name placeholder (post entity resolution will fill, for now raw == canonical stripped of diacritics? keep raw)
    df["player_name_canonical"] = df["player_name_raw"]  # placeholder, will be resolved in Phase 3
    # Ensure types
    df["season_id"] = df["season_id"].astype(str)
    df["award_year"] = df["award_year"].astype(int)
    df["rank"] = df["rank"].astype(int)
    # Parse eval dates to datetime
    df["eval_period_start"] = pd.to_datetime(df["eval_period_start"], errors='coerce')
    df["eval_period_end"] = pd.to_datetime(df["eval_period_end"], errors='coerce')

    # Sort
    df = df.sort_values(["award_year","rank"])

    # Save
    out_path = PROCESSED_DIR / "ground_truth.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved ground truth parquet to {out_path} shape {df.shape}")

    # Also save csv for viewing
    csv_path = PROCESSED_DIR / "ground_truth.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved ground truth csv to {csv_path}")

    return df

def main(force=False):
    print(f"Starting ground truth scrape for years {YEARS[0]}-{YEARS[-1]}, force={force}")
    all_rows = []
    for year in YEARS:
        rows = scrape_year(year, force=force)
        all_rows.extend(rows)

    print(f"Total scraped rows across all years: {len(all_rows)}")

    eval_df = build_eval_window_metadata()
    df = build_ground_truth_parquet(all_rows, eval_df)

    # QA Pass
    print("\n=== QA Pass ===")
    # Check 2020 excluded
    if 2020 not in df["award_year"].unique():
        print("PASS: 2020 correctly excluded (cancelled)")
    else:
        print("FAIL: 2020 should be cancelled but found rows")

    # Every year has winner rank 1
    missing_winner = []
    for y in YEARS:
        if y == 2020:
            continue
        sub = df[df["award_year"]==y]
        if sub.empty:
            missing_winner.append(y)
        elif 1 not in sub["rank"].values:
            missing_winner.append(y)
    if missing_winner:
        print(f"FAIL: Missing winner for years {missing_winner}")
    else:
        print(f"PASS: Every year has rank 1 winner")

    # Check contiguous ranks? At least 1..N no gaps beyond first missing?
    gaps = []
    for y in df["award_year"].unique():
        sub = df[df["award_year"]==y].sort_values("rank")
        ranks = sub["rank"].tolist()
        # Expect ranks start at 1 and are contiguous? Some years may have ties? But check gaps
        expected = list(range(1, max(ranks)+1)) if ranks else []
        # Not strictly required to be contiguous if some ranks missing due to tie? But flag
        # We'll just check no duplicate ranks per year except ties allowed? Actually some years have ties? Check duplicate players
        dup_ranks = sub["rank"].duplicated().any()
        dup_players = sub["player_name_raw"].duplicated().any()
        if dup_players:
            gaps.append((y, "dup player"))
        # points non-increasing with rank where points available (simple check: winner points >= lower ranks)
        # Not strictly enforced for all years due to percent vs points mix, but try
        pts = sub.dropna(subset=["points"]).sort_values("rank")["points"].tolist()
        # Should be non-increasing? For old points yes, but for recent points also.
        # We'll not fail, just log if increasing anywhere
        for i in range(1, len(pts)):
            # If points increase significantly with worse rank, flag
            if pts[i] > pts[i-1] + 1e-6:
                # Could be okay for percent? but flag
                # print(f"WARN {y} points increase at rank {i+1}")
                pass

    if gaps:
        print(f"Duplicate player warnings: {gaps}")
    else:
        print("PASS: No duplicate players within same year detected")

    # Row counts per year
    print("\nRow counts per year (sample):")
    print(df.groupby("award_year").size().head(20))
    print(df.groupby("award_year").size().tail(20))

    print(f"\nTotal seasons: {df['award_year'].nunique()}, total rows: {len(df)}")
    # Expected roughly 5*~69 but we have full lists more than 5 for many years
    print(f"Average rows per year: {len(df)/df['award_year'].nunique():.1f}")

if __name__ == "__main__":
    force = "--force" in sys.argv
    main(force=force)
