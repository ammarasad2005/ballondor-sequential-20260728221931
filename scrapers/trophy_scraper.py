"""
Trophy / Competition Results Scraper
Phase 2 — Team/Trophy Outcomes

Scrapes:
- UCL / European Cup winners by season (Wikipedia)
- World Cup winners by year
- Euros winners by year
- Copa America winners by year (primary international tournaments relevant to Ballon d'Or)
- Domestic league winners (English, Spanish, German, Italian, French top flights) by season

Outputs to data/raw/trophies/ as JSONL and processed CSVs for feature engineering

Idempotent, checkpointed, with rate limiting.
"""

import requests, pandas as pd, time, json, re
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
RAW_DIR = BASE / "data" / "raw" / "trophies"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR = BASE / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent":"Mozilla/5.0 BallonDor Research Bot 0.1 - academic research"}

def fetch_wikipedia_table(url, table_idx_hint=None):
    print(f"Fetching {url}")
    r=requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code!=200:
        print(f"  Failed {r.status_code}")
        return None, None
    html=r.text
    try:
        tables=pd.read_html(html)
    except Exception as e:
        print(f"  pd.read_html failed {e}")
        return None, html
    return tables, html

def scrape_ucl():
    """Scrape UCL / European Cup winners list"""
    url="https://en.wikipedia.org/wiki/List_of_European_Cup_and_UEFA_Champions_League_finals"
    tables,_=fetch_wikipedia_table(url)
    if tables is None:
        return pd.DataFrame()
    # Find table with Year, Winners, etc
    for idx, df in enumerate(tables):
        cols=[str(c).lower() for c in df.columns]
        if any('season' in c or 'year' in c for c in cols) and any('winner' in c or 'champion' in c for c in cols):
            print(f"  UCL table found idx {idx} cols {df.columns.tolist()} shape {df.shape}")
            # Clean
            # Example columns: Season, Winners, Score, Runners-up...
            # We'll parse Year
            # Try to extract year and winner
            # The table may have Season like "1955–56"
            # Winner may contain club name
            # Save raw
            out=RAW_DIR/"ucl_finals_raw.csv"
            df.to_csv(out, index=False)
            # Parse to structured
            # Extract winner
            # If column names are MultiIndex, flatten
            # Try to identify winner column
            winner_col=None
            season_col=None
            runner_col=None
            for c in df.columns:
                cl=str(c).lower()
                if 'winner' in cl or 'champion' in cl:
                    winner_col=c
                elif 'season' in cl or 'year' in cl:
                    season_col=c
                elif 'runner' in cl or 'runners' in cl:
                    runner_col=c
            if winner_col and season_col:
                parsed=[]
                for _, row in df.iterrows():
                    season_raw=str(row[season_col])
                    season=season_raw.strip()
                    # Clean season string: remove footnotes
                    season_clean=re.sub(r'\[.*?\]','',season).strip()
                    year=None
                    # For UCL finals, Season like "2023–24" means final in 2024, so year should be end year
                    # Strategy: split by dash (en dash or hyphen) and take last part as year indicator
                    # Handle both 4-digit and 2-digit second part
                    try:
                        # Normalize dash
                        season_norm=season_clean.replace('–','-').replace('—','-')
                        if '-' in season_norm:
                            parts=season_norm.split('-')
                            # Last part may contain year like "24" or "2024" or " 24 (details)"
                            last_part=parts[-1].strip()
                            # Extract 2 or 4 digit year from last part
                            m_last=re.search(r'(\d{4})', last_part)
                            if m_last:
                                year=int(m_last.group(1))
                            else:
                                m2=re.search(r'(\d{2})\b', last_part)
                                if m2:
                                    two=int(m2.group(1))
                                    # Infer century from first part
                                    first_part=parts[0]
                                    m_first=re.search(r'(\d{4})', first_part)
                                    if m_first:
                                        first_year=int(m_first.group(1))
                                        century=first_year//100
                                        year=century*100+two
                                        if year < first_year:
                                            year+=100
                                        # Handle 1999-00
                                        if two==0:
                                            year=first_year+1
                                    else:
                                        # Fallback: assume 2000s if two <50 else 1900s
                                        year=2000+two if two<50 else 1900+two
                                else:
                                    # No year in last part, fallback to first part
                                    m_first=re.search(r'(\d{4})', season_norm)
                                    if m_first:
                                        # For range like "1955–56" we want end year, but if last part parsing failed, use first year+1 as approx
                                        first_year=int(m_first.group(1))
                                        year=first_year+1
                        else:
                            # Single year like "2024"
                            m=re.search(r'(\d{4})', season_clean)
                            if m:
                                year=int(m.group(1))
                    except Exception as e:
                        # Fallback: find last 4-digit year in string
                        years=re.findall(r'\d{4}', season_clean)
                        if years:
                            year=int(years[-1])

                    winner=str(row[winner_col]) if winner_col in row else None
                    runner=str(row[runner_col]) if runner_col and runner_col in row else None
                    winner=re.sub(r'\[.*?\]','',winner).strip()
                    if year and winner:
                        parsed.append({"season":season_raw, "year":year, "winner_club":winner, "runner_up":runner, "source":url})
                df_parsed=pd.DataFrame(parsed)
                df_parsed=df_parsed.sort_values("year")
                # Save
                out2=RAW_DIR/"ucl_winners_parsed.csv"
                df_parsed.to_csv(out2,index=False)
                print(f"  Parsed {len(df_parsed)} UCL winners")
                return df_parsed
    print("  UCL table not found")
    return pd.DataFrame()

def scrape_world_cup():
    url="https://en.wikipedia.org/wiki/List_of_FIFA_World_Cup_finals"
    tables,_=fetch_wikipedia_table(url)
    if tables is None:
        return pd.DataFrame()
    for idx, df in enumerate(tables):
        cols=[str(c).lower() for c in df.columns]
        if any('year' in c for c in cols) and any('winner' in c for c in cols):
            print(f"  World Cup table idx {idx} cols {df.columns.tolist()} shape {df.shape}")
            # Save raw
            df.to_csv(RAW_DIR/"worldcup_finals_raw.csv",index=False)
            # Parse
            year_col=None
            winner_col=None
            for c in df.columns:
                cl=str(c).lower()
                if 'year' in cl:
                    year_col=c
                if 'winner' in cl:
                    winner_col=c
            if year_col and winner_col:
                parsed=[]
                for _, row in df.iterrows():
                    y=row[year_col]
                    # y may be year or contain year
                    try:
                        year_int=int(re.search(r'(\d{4})', str(y)).group(1))
                    except:
                        continue
                    winner=str(row[winner_col])
                    winner=re.sub(r'\[.*?\]','',winner).strip()
                    parsed.append({"year":year_int, "winner_country":winner, "source":url})
                df_p=pd.DataFrame(parsed)
                df_p.to_csv(RAW_DIR/"worldcup_winners_parsed.csv",index=False)
                print(f"  Parsed {len(df_p)} World Cup winners")
                return df_p
    return pd.DataFrame()

def scrape_euros():
    url="https://en.wikipedia.org/wiki/UEFA_European_Championship"
    tables,_=fetch_wikipedia_table(url)
    if tables is None:
        # Try alternative list page
        url2="https://en.wikipedia.org/wiki/List_of_UEFA_European_Championship_finals"
        tables,_=fetch_wikipedia_table(url2)
        if tables is None:
            return pd.DataFrame()
        url=url2
    for idx, df in enumerate(tables):
        cols=[str(c).lower() for c in df.columns]
        if any('year' in c for c in cols) and any('winner' in c or 'champion' in c for c in cols):
            print(f"  Euros table idx {idx} cols {df.columns.tolist()} shape {df.shape}")
            df.to_csv(RAW_DIR/"euros_finals_raw.csv",index=False)
            year_col=None
            winner_col=None
            for c in df.columns:
                cl=str(c).lower()
                if 'year' in cl:
                    year_col=c
                if 'winner' in cl or 'champion' in cl:
                    winner_col=c
            if year_col and winner_col:
                parsed=[]
                for _, row in df.iterrows():
                    y=row[year_col]
                    try:
                        year_int=int(re.search(r'(\d{4})', str(y)).group(1))
                    except:
                        continue
                    winner=str(row[winner_col])
                    winner=re.sub(r'\[.*?\]','',winner).strip()
                    parsed.append({"year":year_int, "winner_country":winner, "source":url})
                df_p=pd.DataFrame(parsed)
                df_p.to_csv(RAW_DIR/"euros_winners_parsed.csv",index=False)
                print(f"  Parsed {len(df_p)} Euros winners")
                return df_p
    return pd.DataFrame()

def scrape_copa_america():
    url="https://en.wikipedia.org/wiki/List_of_Copa_Am%C3%A9rica_finals"
    tables,_=fetch_wikipedia_table(url)
    if tables is None:
        return pd.DataFrame()
    for idx, df in enumerate(tables):
        cols=[str(c).lower() for c in df.columns]
        if any('year' in c for c in cols) and any('winner' in c for c in cols):
            print(f"  Copa table idx {idx} cols {df.columns.tolist()} shape {df.shape}")
            df.to_csv(RAW_DIR/"copa_finals_raw.csv",index=False)
            year_col=None
            winner_col=None
            for c in df.columns:
                cl=str(c).lower()
                if 'year' in cl and 'extra' not in cl:
                    year_col=c
                if 'winner' in cl:
                    winner_col=c
            if year_col and winner_col:
                parsed=[]
                for _, row in df.iterrows():
                    y=row[year_col]
                    try:
                        # Year may have range
                        year_int=int(re.search(r'(\d{4})', str(y)).group(1))
                    except:
                        continue
                    winner=str(row[winner_col])
                    winner=re.sub(r'\[.*?\]','',winner).strip()
                    parsed.append({"year":year_int, "winner_country":winner, "source":url})
                df_p=pd.DataFrame(parsed)
                df_p.to_csv(RAW_DIR/"copa_winners_parsed.csv",index=False)
                print(f"  Parsed {len(df_p)} Copa winners")
                return df_p
    return pd.DataFrame()

def scrape_domestic_leagues():
    """Scrape league winners for top 5 leagues - simple approach via Wikipedia pages"""
    leagues={
        "Premier League": "https://en.wikipedia.org/wiki/List_of_English_football_champions",
        "La Liga": "https://en.wikipedia.org/wiki/List_of_Spanish_football_champions",
        "Bundesliga": "https://en.wikipedia.org/wiki/List_of_German_football_champions",
        "Serie A": "https://en.wikipedia.org/wiki/List_of_Italian_football_champions",
        "Ligue 1": "https://en.wikipedia.org/wiki/List_of_French_football_champions"
    }
    all_parsed=[]
    for league, url in leagues.items():
        tables,_=fetch_wikipedia_table(url)
        time.sleep(1)
        if tables is None:
            continue
        # Find table with season/year and champions
        for idx, df in enumerate(tables):
            cols=[str(c).lower() for c in df.columns]
            if any('season' in c or 'year' in c for c in cols) and any('champion' in c or 'winner' in c for c in cols):
                print(f"  {league} table idx {idx} cols {df.columns.tolist()} shape {df.shape}")
                # Save raw
                safe_name=league.replace(' ','_')
                df.to_csv(RAW_DIR/f"{safe_name}_raw.csv",index=False)
                # Parse
                season_col=None
                winner_col=None
                for c in df.columns:
                    cl=str(c).lower()
                    if ('season' in cl or 'year' in cl) and season_col is None:
                        season_col=c
                    if ('champion' in cl or 'winner' in cl) and winner_col is None:
                        winner_col=c
                if season_col and winner_col:
                    for _, row in df.iterrows():
                        season=str(row[season_col])
                        winner=str(row[winner_col])
                        # Extract year
                        # For season like "2023–24", use end year
                        try:
                            years=re.findall(r'\d{4}', season)
                            if not years:
                                # Try 2-digit second year pattern like "2023-24"
                                m=re.search(r'(\d{4})[–-](\d{2})', season)
                                if m:
                                    first=int(m.group(1))
                                    second_two=int(m.group(2))
                                    # infer
                                    century=first//100
                                    second=century*100+second_two
                                    if second < first:
                                        second+=100
                                    year=second
                                else:
                                    continue
                            else:
                                # Use last year in list as season end
                                if len(years)>=2:
                                    year=int(years[-1])
                                else:
                                    # If only one year like "2023", use that
                                    year=int(years[0])
                        except:
                            continue
                        winner=re.sub(r'\[.*?\]','',winner).strip()
                        if winner and year:
                            all_parsed.append({"league":league, "season":season, "year":year, "winner_club":winner, "source":url})
                    break
    df=pd.DataFrame(all_parsed)
    if not df.empty:
        df.to_csv(RAW_DIR/"domestic_leagues_parsed.csv",index=False)
        print(f"  Parsed {len(df)} domestic league winners across leagues")
    return df

def main():
    print("Starting trophy scraper")
    dfs=[]
    ucl=scrape_ucl()
    if not ucl.empty:
        dfs.append(("ucl", ucl))
    time.sleep(1)
    wc=scrape_world_cup()
    if not wc.empty:
        dfs.append(("worldcup", wc))
    time.sleep(1)
    euros=scrape_euros()
    if not euros.empty:
        dfs.append(("euros", euros))
    time.sleep(1)
    copa=scrape_copa_america()
    if not copa.empty:
        dfs.append(("copa", copa))
    time.sleep(1)
    domestic=scrape_domestic_leagues()
    if not domestic.empty:
        dfs.append(("domestic", domestic))

    # Combine for processed output? We'll save individual parquet files
    for name, df in dfs:
        if not df.empty:
            out_path=PROCESSED_DIR/f"trophy_{name}.parquet"
            try:
                df.to_parquet(out_path,index=False)
                print(f"Saved {name} to {out_path}")
            except Exception as e:
                # fallback csv
                df.to_csv(PROCESSED_DIR/f"trophy_{name}.csv",index=False)
                print(f"Saved {name} csv fallback due {e}")

    # Create combined trophy timeline for easy joining later
    # For Ballon d'Or features, we need to know for each season whether player's club won league, UCL, etc, and whether player's nation won World Cup/Euro/Copa in relevant calendar year
    # We'll produce a unified file later in feature engineering, but for now checkpoint raw

    print("Trophy scraper finished")

if __name__=="__main__":
    main()
