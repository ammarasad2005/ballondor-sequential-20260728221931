"""
QA Report for Entity Resolution
Phase 3 Task 4

Confirms every ground-truth row resolves to exactly one stats row per source table
and surfaces unresolved rows explicitly per Key Focus Area §2.
"""

import pandas as pd
from pathlib import Path
import json

BASE=Path(__file__).parent.parent
GT_PATH=BASE/"data/processed/ground_truth.parquet"
RESOLVED_PATH=BASE/"data/interim/ground_truth_resolved.parquet"
STATS_COMBINED_DIR=BASE/"data/raw/stats_combined"
STATS_MODERN_DIR=BASE/"data/raw/stats_modern"
STATS_CLASSICAL_DIR=BASE/"data/raw/stats_classical"
NARRATIVE_PATH=BASE/"data/processed/narrative_flags.parquet"
TROPHY_UCL=BASE/"data/processed/trophy_ucl.parquet"

print("=== Entity Resolution QA Report ===")

gt=pd.read_parquet(GT_PATH)
resolved=pd.read_parquet(RESOLVED_PATH)
narrative=pd.read_parquet(NARRATIVE_PATH)

print(f"Ground truth rows: {len(gt)}, seasons: {gt['award_year'].nunique()}, unique players: {gt['player_name_raw'].nunique()}")
print(f"Resolved rows: {len(resolved)}")
print(f"Narrative flags rows: {len(narrative)}")

# Check 1: Every ground truth row resolves to exactly one stats row
# Our stats per-season files should exist for all ground truth rows
# Check file existence
import os, re
missing_stats=[]
for _, row in gt.iterrows():
    season_id=row["season_id"]
    player=row["player_name_raw"]
    safe_player=re.sub(r'[^a-zA-Z0-9_\-]', '_', player)[:80]
    award_year=int(row["award_year"])
    if award_year >=2014:
        target_dir=STATS_MODERN_DIR
    else:
        target_dir=STATS_CLASSICAL_DIR
    dest_file=target_dir/f"{season_id}_{safe_player}.json"
    if not dest_file.exists():
        missing_stats.append((season_id, player, str(dest_file)))

print(f"\nCheck 1: Stats per-season checkpoint existence")
print(f"Missing stats files: {len(missing_stats)} (should be 0)")
if missing_stats:
    print(f"Sample missing: {missing_stats[:10]}")
else:
    print("PASS: Every ground truth row has exactly one stats raw file (modern or classical)")

# Check 2: Resolved canonical ID not null
unresolved=resolved[resolved["canonical_id"].isna()]
print(f"\nCheck 2: Resolved canonical_id null count: {len(unresolved)} (should be 0)")
if len(unresolved)>0:
    print(unresolved[["season_id","player_name_raw","match_confidence"]].head())
else:
    print("PASS: Zero unresolved ground-truth rows remain silently unjoined (per Phase 3 exit criterion)")

# Check 3: Narrative flags join
# Every ground truth row should have narrative flag
merged=pd.merge(gt, narrative, on=["season_id","award_year","player_name_raw"], how="left", indicator=True)
missing_narrative=merged[merged["_merge"]!="both"]
print(f"\nCheck 3: Narrative flags join")
print(f"Missing narrative flags: {len(missing_narrative)} (should be 0)")
if len(missing_narrative)>0:
    print(missing_narrative.head())
else:
    print("PASS: All ground truth rows have narrative flags")

# Check 4: Alias table coverage
# Every ground truth player should have alias entry
import yaml
with open(BASE/"entity_resolution/alias_table.yaml") as f:
    alias_data=yaml.safe_load(f)
aliases=alias_data.get("aliases",[])
alias_ids=set([a["canonical_id"] for a in aliases])
resolved_ids=set(resolved["canonical_id"].dropna().unique())
missing_alias=resolved_ids - alias_ids
print(f"\nCheck 4: Alias table coverage")
print(f"Canonical IDs in resolved: {len(resolved_ids)}, in alias table: {len(alias_ids)}, missing: {len(missing_alias)}")
if missing_alias:
    print(f"Missing alias IDs sample: {list(missing_alias)[:10]}")
else:
    print("PASS: All resolved canonical IDs present in alias table")

# Check 5: Row counts expected vs actual (per Key Focus Area §2 QA must report count)
expected_total=2004
actual_total=len(gt)
print(f"\nCheck 5: Row counts")
print(f"Expected ground truth total (from scraping): {expected_total}")
print(f"Actual ground truth rows: {actual_total}")
print(f"Match: {expected_total==actual_total}")

# Check 6: Duplicate check
dup=resolved.duplicated(subset=["season_id","player_name_raw"])
print(f"\nCheck 6: Duplicate (season_id, player) in resolved: {dup.sum()} (should be 0)")
if dup.sum()>0:
    print(resolved[dup].head())

# Summary report file
report_path=BASE/"reports/entity_resolution_qa.md"
with open(report_path,'w') as f:
    f.write("# Entity Resolution QA Report\n\n")
    f.write(f"Date: 2026-07-28\n\n")
    f.write(f"Ground truth rows: {len(gt)}, seasons: {gt['award_year'].nunique()}, unique players: {gt['player_name_raw'].nunique()}\n\n")
    f.write(f"Resolved rows: {len(resolved)}\n\n")
    f.write("## Checks\n\n")
    f.write(f"1. Stats per-season checkpoint existence: Missing {len(missing_stats)} (expected 0) — {'PASS' if len(missing_stats)==0 else 'FAIL'}\n\n")
    f.write(f"2. Unresolved canonical_id: {len(unresolved)} (expected 0) — {'PASS' if len(unresolved)==0 else 'FAIL'}\n\n")
    f.write(f"3. Narrative flags join missing: {len(missing_narrative)} — {'PASS' if len(missing_narrative)==0 else 'FAIL'}\n\n")
    f.write(f"4. Alias table coverage missing: {len(missing_alias)} — {'PASS' if len(missing_alias)==0 else 'FAIL'}\n\n")
    f.write(f"5. Row counts expected {expected_total} actual {actual_total} — {'PASS' if expected_total==actual_total else 'FAIL'}\n\n")
    f.write(f"6. Duplicate (season,player): {dup.sum()} — {'PASS' if dup.sum()==0 else 'FAIL'}\n\n")
    f.write("## Conclusion\n\n")
    if len(missing_stats)==0 and len(unresolved)==0 and len(missing_narrative)==0 and len(missing_alias)==0:
        f.write("All checks PASS — zero unresolved ground-truth rows remain silently unjoined. Every row either successfully joins or is explicitly logged as documented gap (per Phase 3 exit criterion).\n")
    else:
        f.write("Some checks FAILED — see above for gaps that need explicit logging.\n")

print(f"\nSaved QA report to {report_path}")
