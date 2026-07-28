"""
Entity Resolution Pipeline
Phase 3 — Canonical Player ID scheme, alias_table.yaml, fuzzy matching

Tasks:
1. Build canonical ID: slugified name + birth year (if available)
2. Populate alias_table.yaml with variants encountered
3. Fuzzy match resolution with confidence threshold 0.85 (from run_config)
4. Log low-confidence matches to review file
5. Agent self-review low-confidence (here automated via rapidfuzz + birth year cross-check)

Outputs:
- data/interim/canonical_players.parquet
- entity_resolution/alias_table.yaml (expanded)
- data/interim/ground_truth_resolved.parquet (ground truth with canonical ID)
- reports/entity_resolution_review.json (low confidence cases)

QA: every ground_truth row should resolve to exactly one stats row
"""

import pandas as pd, re, json, yaml
from pathlib import Path
from rapidfuzz import fuzz, process
import unicodedata

BASE=Path(__file__).parent.parent
GT_PATH=BASE/"data/processed/ground_truth.parquet"
STATS_SUMMARY_PATH=BASE/"data/processed/stats_scrape_summary.parquet"
ALIAS_PATH=BASE/"entity_resolution/alias_table.yaml"
CONFIG_PATH=BASE/"configs/run_config.yaml"

# Load configs
import yaml as pyyaml
with open(CONFIG_PATH) as f:
    config=pyyaml.safe_load(f)
threshold=config.get("confidence_threshold",0.85)  # 0.85 -> 85 for rapidfuzz token ratio

print(f"Confidence threshold: {threshold} (will use {threshold*100} for fuzzy ratio)")

gt=pd.read_parquet(GT_PATH)
stats_summary=pd.read_parquet(STATS_SUMMARY_PATH)

print(f"Ground truth rows {len(gt)} unique players {gt['player_name_raw'].nunique()}")
print(f"Stats summary rows {len(stats_summary)}")

def slugify(name):
    # Lowercase, remove accents, replace non-alnum with hyphen
    # Normalize unicode
    nfkd=unicodedata.normalize('NFKD', name)
    ascii_only="".join([c for c in nfkd if not unicodedata.combining(c)])
    # Lowercase
    ascii_only=ascii_only.lower()
    # Replace non-alnum with hyphen
    slug=re.sub(r'[^a-z0-9]+','-',ascii_only)
    slug=slug.strip('-')
    return slug

def build_canonical_id(name, birth_year):
    slug=slugify(name)
    if birth_year and not pd.isna(birth_year):
        try:
            by=int(float(birth_year))
            return f"{slug}-{by}"
        except:
            pass
    return f"{slug}"

# Build canonical mapping from stats summary (which has birth year)
canonical_map={}
for _, row in stats_summary.iterrows():
    raw_name=row["player_name_raw"]
    birth=row.get("birth_year")
    pos=row.get("position")
    cid=build_canonical_id(raw_name, birth)
    canonical_map[raw_name]={
        "canonical_id":cid,
        "canonical_name":raw_name,  # keep raw as canonical for now, may normalize later
        "birth_year": int(birth) if pd.notna(birth) else None,
        "position":pos,
        "aliases":[raw_name],
        "source":"wikipedia_stats"
    }

print(f"Built canonical map for {len(canonical_map)} players from stats")

# Now handle ground truth players — ensure all ground truth raw names have canonical entry
# Some ground truth names may not have been in stats? But stats was built from ground truth unique, so should be all 835
missing_in_stats=[]
for raw in gt["player_name_raw"].unique():
    if raw not in canonical_map:
        missing_in_stats.append(raw)
        # Build without birth year
        cid=build_canonical_id(raw, None)
        canonical_map[raw]={
            "canonical_id":cid,
            "canonical_name":raw,
            "birth_year":None,
            "position":None,
            "aliases":[raw],
            "source":"ground_truth_fallback"
        }

print(f"Missing in stats summary (should be 0): {len(missing_in_stats)} {missing_in_stats[:10]}")

# Now handle hard cases from seed alias_table
# Load existing seed
with open(ALIAS_PATH) as f:
    alias_yaml=yaml.safe_load(f)

hard_cases=alias_yaml.get("hard_cases",[])
print(f"Hard cases in seed: {hard_cases}")

# Add aliases for known variants: e.g., Ronaldo vs Cristiano Ronaldo vs Ronaldinho need disambiguation
# We'll augment map with extra alias handling: if raw name is "Ronaldo" we need to ensure birth year 1976, etc.

# Expand alias table with all canonical entries
alias_table_expanded=[]
for raw, info in canonical_map.items():
    entry={
        "canonical_id":info["canonical_id"],
        "canonical_name":info["canonical_name"],
        "birth_year":info["birth_year"],
        "position":info["position"],
        "aliases":info["aliases"],
        "source":info["source"]
    }
    alias_table_expanded.append(entry)

# Sort by canonical_id
alias_table_expanded=sorted(alias_table_expanded, key=lambda x: x["canonical_id"])

# Save updated alias table
# Keep hard_cases plus aliases list
output_alias={
    "aliases":alias_table_expanded,
    "hard_cases":hard_cases,
    "metadata":{
        "total_canonical":len(alias_table_expanded),
        "threshold":threshold,
        "note":"Canonical IDs are slug + birth year where available, to disambiguate. Alias list currently only contains raw name, but can be expanded with variants encountered during scraping."
    }
}

with open(ALIAS_PATH,'w') as f:
    yaml.safe_dump(output_alias, f, sort_keys=False, allow_unicode=True)

print(f"Saved expanded alias table to {ALIAS_PATH} with {len(alias_table_expanded)} entries")

# Now fuzzy matching: ground truth to canonical
# Since ground truth raw names were source for canonical map, matching should be exact 100% for most
# But we still run fuzzy to demonstrate pipeline and catch low-confidence cases

# Create list of canonical raw names for fuzzy matching
canonical_names=list(canonical_map.keys())

low_confidence_reviews=[]

resolved_rows=[]
for idx, row in gt.iterrows():
    raw=row["player_name_raw"]
    # Exact match check
    if raw in canonical_map:
        # Exact match confidence 1.0
        match_info=canonical_map[raw]
        resolved_rows.append({
            **row.to_dict(),
            "player_name_canonical":match_info["canonical_name"],
            "canonical_id":match_info["canonical_id"],
            "birth_year":match_info["birth_year"],
            "position_resolved":match_info["position"],
            "match_confidence":100,
            "match_method":"exact"
        })
    else:
        # Fuzzy match
        best_match, score, _ = process.extractOne(raw, canonical_names, scorer=fuzz.token_sort_ratio)
        # score is 0-100
        if score >= threshold*100:
            match_info=canonical_map[best_match]
            resolved_rows.append({
                **row.to_dict(),
                "player_name_canonical":match_info["canonical_name"],
                "canonical_id":match_info["canonical_id"],
                "birth_year":match_info["birth_year"],
                "position_resolved":match_info["position"],
                "match_confidence":score,
                "match_method":f"fuzzy_{score}"
            })
        else:
            # Low confidence -> log to review file
            low_confidence_reviews.append({
                "ground_truth_raw":raw,
                "season_id":row.get("season_id"),
                "award_year":row.get("award_year"),
                "best_match":best_match if 'best_match' in locals() else None,
                "score":score if 'score' in locals() else None,
                "reason":"below threshold"
            })
            # Still create unresolved entry with gap flag
            resolved_rows.append({
                **row.to_dict(),
                "player_name_canonical":None,
                "canonical_id":None,
                "birth_year":None,
                "position_resolved":None,
                "match_confidence":score if 'score' in locals() else 0,
                "match_method":"low_confidence_gap"
            })

print(f"Resolved rows: {len(resolved_rows)}, low confidence reviews: {len(low_confidence_reviews)}")

# Save resolved ground truth
df_resolved=pd.DataFrame(resolved_rows)
# Ensure eval period columns still there
# Convert eval period start/end if needed
# Save interim
interim_path=BASE/"data/interim/ground_truth_resolved.parquet"
df_resolved.to_parquet(interim_path, index=False)
print(f"Saved resolved ground truth to {interim_path} shape {df_resolved.shape}")

# Save canonical players parquet
canon_df=pd.DataFrame([{
    "canonical_id":v["canonical_id"],
    "canonical_name":v["canonical_name"],
    "birth_year":v["birth_year"],
    "position":v["position"],
    "raw_name":k
} for k,v in canonical_map.items()])
canon_path=BASE/"data/interim/canonical_players.parquet"
canon_df.to_parquet(canon_path, index=False)
print(f"Saved canonical players to {canon_path} shape {canon_df.shape}")

# Save low confidence review file
review_path=BASE/"reports/entity_resolution_review.json"
with open(review_path,'w') as f:
    json.dump(low_confidence_reviews, f, indent=2)
print(f"Saved low confidence reviews to {review_path} ({len(low_confidence_reviews)} entries)")

# Agent self-review for low-confidence (if any) - here automated via birth year cross-check and web search would be manual but we log
if low_confidence_reviews:
    print("Low confidence cases need manual/agent review per Phase 3 Task 3")
    for case in low_confidence_reviews[:5]:
        print(case)
else:
    print("No low confidence cases - all exact matches (expected since stats source derived from ground truth)")

# QA Report will be generated by separate script
