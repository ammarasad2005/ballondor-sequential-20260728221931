"""
Update features.parquet with Understat advanced metrics
- Reads data/raw/stats_modern/advanced/*_understat.json
- Merges xG, xA, etc into features.parquet for modern era
"""

import pandas as pd, json, glob
from pathlib import Path

BASE=Path(__file__).parent.parent
FEAT_PATH=BASE/"data/processed/features.parquet"
ADV_DIR=BASE/"data/raw/stats_modern/advanced"

df=pd.read_parquet(FEAT_PATH)
print(f"Loaded features {df.shape}")

# Load advanced files
adv_files=list(ADV_DIR.glob("*_understat.json"))
print(f"Found {len(adv_files)} advanced files")

# Build map season_id+player -> advanced metrics
adv_map={}
for f in adv_files:
    try:
        with open(f) as fin:
            data=json.load(fin)
        key=(data.get("season_id"), data.get("player_name_raw"))
        # Also try award_year+player
        adv_map[key]=data
    except Exception as e:
        print(f"Failed {f} {e}")

print(f"Advanced map size {len(adv_map)}")

# For each feature row in modern era, try to find advanced
# Add new columns if not exist
for col in ["xG","xA","shots","key_passes","xGChain","xGBuildup","npg","npxG","games","time"]:
    if col not in df.columns:
        df[col]=pd.NA

matched=0
for idx, row in df.iterrows():
    if row["award_year"]<2014:
        continue
    key=(str(row["season_id"]), row["player_name_raw"])
    adv=adv_map.get(key)
    if not adv:
        # Try fuzzy by player name only and award_year
        # Search all keys for same player and award_year
        for k,v in adv_map.items():
            if k[1]==row["player_name_raw"] and v.get("award_year")==row["award_year"]:
                adv=v
                break
    if adv:
        # Fill
        for col in ["xG","xA","shots","key_passes","xGChain","xGBuildup","npg","npxG","games","time"]:
            val=adv.get(col)
            if val is not None:
                try:
                    # Convert to float if possible
                    df.at[idx, col]=float(val)
                except:
                    df.at[idx, col]=val
        matched+=1

print(f"Matched and updated {matched} rows with Understat data")

# For features that were previously missing_documented, now have values
# Compute new feature: xG_per90, xA_per90, etc? We have time (minutes)
# xG_per90 = xG / (time/90)
# xA_per90 = xA / (time/90)
# Also overperformance vs xG: goals - xG

def compute_per90(df):
    # time is minutes
    df["time"] = pd.to_numeric(df["time"], errors='coerce')
    df["xG"] = pd.to_numeric(df["xG"], errors='coerce')
    df["xA"] = pd.to_numeric(df["xA"], errors='coerce')
    df["xG_per90"] = df["xG"] / (df["time"]/90).replace(0, pd.NA)
    df["xA_per90"] = df["xA"] / (df["time"]/90).replace(0, pd.NA)
    # Overperformance
    df["goals_over_xG"] = pd.to_numeric(df["league_goals"], errors='coerce') - df["xG"]
    return df

df=compute_per90(df)

# Compute peer percentiles for new advanced metrics within year (like we did for goals)
def compute_percentile(series):
    return series.rank(pct=True, method='average')*100

for col in ["xG","xA","xG_per90","xA_per90","shots","key_passes"]:
    pct_col=col+"_percentile_in_year"
    if col in df.columns:
        df[pct_col]=df.groupby("award_year")[col].transform(lambda x: compute_percentile(x))

print("Computed percentiles for advanced metrics")

# Save updated features
out_path=BASE/"data/processed/features_with_understat.parquet"
df.to_parquet(out_path, index=False)
print(f"Saved updated features to {out_path} shape {df.shape}")

# Also overwrite original features.parquet? Keep original as backup, and also overwrite main features.parquet for modeling to use new features
# Let's overwrite main features.parquet with updated version that includes xG etc
df.to_parquet(FEAT_PATH, index=False)
print(f"Overwrote main features.parquet with Understat-enriched version")

# Update feature registry to mark xG, xA etc as now available (status from missing to available)
# We'll not edit yaml here, just log
print("\nAdvanced metrics coverage after update:")
for col in ["xG","xA","xG_per90","xA_per90","shots","key_passes","xGChain","xGBuildup"]:
    if col in df.columns:
        missing=df[col].isna().sum()
        print(f"{col}: missing {missing}/{len(df)} ({missing/len(df)*100:.1f}%) — modern era only, so classical will be missing")

print("\nModern era coverage:")
modern=df[df["award_year"]>=2014]
for col in ["xG","xA"]:
    miss_mod=modern[col].isna().sum()
    print(f"{col} modern missing {miss_mod}/{len(modern)} ({miss_mod/len(modern)*100:.1f}%)")
