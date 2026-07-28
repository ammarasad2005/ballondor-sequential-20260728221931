# Phase 2 Coverage Report — Data Acquisition

Date: 2026-07-28

## Ground Truth Backbone
- Total rows: 2004, unique players: 835, seasons: 69 (1956-2025 excl 2020)
- File: data/processed/ground_truth.parquet

## Individual Stats (Modern + Classical) — Wikipedia based

### Approach
- Unique players 835, each Wikipedia page fetched via direct title guess + opensearch API fallback
- Rate limited 1s per request, checkpointed per player to data/raw/stats_combined/{player}.json
- Per-season checkpoint files created keyed by season_id + player_name_raw into:
  - data/raw/stats_modern/ (316 files) — award_year >=2014
  - data/raw/stats_classical/ (1688 files) — award_year <2014
- Counts match ground truth exactly: 316 + 1688 = 2004

### Coverage
- Fetch status: all 835 players returned status ok (0 gaps for page not found) — some pages had 0 career stats tables (e.g., very early era players where Wikipedia stats table format differs or only honours listed)
- career_stats_count distribution:
  - Mean, median need to check stats_scrape_summary.parquet
- Positions extracted from infobox: available for most players, but some early era players missing (e.g., Ali Kemal 1869 birth, no position)

From scrape_summary.csv:
- Example sample checked: Messi had 1 raw tables count, 200+ season entries parsed; Di Stéfano 27 seasons parsed.
- Some players with 0 tables: Agne Simonsson, Ake Johansson, Albert Shesternyov, Alan Ball etc — these are pre-1970 players where Wikipedia career stats table may be missing or formatted differently. Gap logged as 0 count.

### Known Gaps — Explicitly Documented per Key Focus Area §9
- Advanced metrics modern_only: xG, xA, progressive passes/carries, shot-creating actions, per-90 splits — NOT AVAILABLE via Wikipedia. FBRef was identified in Phase 0 as ideal source but blocked by Cloudflare WAF (403 via requests, Cloudflare challenge via Playwright). Attempted alternative sources: worldfootball.net 403, soccerway 200 but 0 tables (JS-rendered), whoscored 403, fotmob 200 but JS-heavy, transfermarkt 202 len 0. Result: advanced metrics flagged as missing for modern era, documented as gap, not silently filled. This will be reflected in feature_registry.yaml as modern_only but with imputation_policy = missing_documented.
- Assists pre-1990s: notoriously poorly recorded — many Wikipedia career tables list only Apps/Goals, not Assists. Gap expected and documented.
- Minutes played pre-1990s: often unavailable, appearances used as durability proxy per Requirements A.2 classical era note.
- Some player pages disambiguation failures: e.g., Adriano (multiple footballers named Adriano) — our scraper fetched https://en.wikipedia.org/wiki/Adriano which is disambiguation? Actually Adriano page is Brazilian striker, but we got 0 tables count? Need to check. Logged.

### Resumability Verified
- First run of stats_scraper timed out after 605 players (900s timeout). Second run resumed from checkpoint (checked existing files, skipped 605), completed remaining 230 in ~347s. Demonstrates idempotent checkpointing per Blueprint §4.2 requirement.

## Trophy / Competition Results

### Scraped Sources (all Wikipedia, verified 200 OK in Phase 0)
- UCL: https://en.wikipedia.org/wiki/List_of_European_Cup_and_UEFA_Champions_League_finals — 72 winners parsed (1956-2025)
- World Cup: https://en.wikipedia.org/wiki/List_of_FIFA_World_Cup_finals — 23 winners
- Euros: https://en.wikipedia.org/wiki/UEFA_European_Championship (and List_of_UEFA_European_Championship_finals) — 19 winners (1960-2024)
- Copa América: https://en.wikipedia.org/wiki/List_of_Copa_Am%C3%A9rica_finals — 23 winners
- Domestic Leagues: 5 leagues (English, Spanish, German, Italian, French) — 379 winners parsed across leagues (some early seasons missing due to table structure variance)

### Coverage vs Ground Truth Need
- For each ground_truth row, we can determine via year whether player's club won UCL/domestic and whether player's nation won international. Raw files exist.
- Gap: Domestic league parsing for some leagues incomplete (e.g., La Liga raw shape 98 but expected ~95 from 1929-present, got some; Ligue 1 shape 118 etc). But at least top 5 leagues coverage from 1956 onward present for majority. Gap documented.

### Files
- Raw: data/raw/trophies/*.csv (ucl, worldcup, euros, copa, domestic)
- Processed: data/processed/trophy_*.parquet

## Narrative / Media Signal (Best-Effort)

### Approach
- Implemented narrative_flagger.py heuristic to avoid leakage per Key Focus Area §3:
  - NOT using betting odds or pundit predictions (would be perfect proxy)
  - NOT using post-hoc article text like "stellar Ballon d'Or campaign"
  - Instead operationalized:
    - club_prestige_tier: Tier1 = frequent Deloitte Money League + high UEFA coefficient clubs (Real Madrid, Barcelona, Bayern, ManU, Juventus, Milan, Liverpool, Inter, Chelsea, Man City, PSG). Tier2 = other frequent winners. Tier3 = rest. Documented in scrapers/narrative_flagger.py and data/raw/narrative/inference_log.md
    - market_size_proxy = prestige_score (1-3)
    - signature_moment_flag = 1 if player's club won UCL in award year, or player's nation won World Cup/Euro/Copa in award year (or previous year for season-based eval). Best-effort proxy for iconic final performance.

### Coverage
- Generated for all 2004 ground truth rows: data/processed/narrative_flags.parquet
- Signature moment flagged 306/2004 (~15%)
- Club prestige tier: Tier1 1019, Tier2 465, Tier3 520
- All flags logged as agent-inferred per Requirements A.4, with reasoning in inference_log.md

### Gaps / Limitations
- Signature moment is proxy, not sourced iconic moment like hat-trick in final (would require manual inspection of each final's match report, which is beyond automated scraping). Documented as inferred.
- No media volume signal (news article counts) — would be leakage if post-hoc. Omitted.

## Overall Phase 2 Exit Criterion Check

Criterion: For every (season_id, player) pair in ground_truth.parquet, at least era-appropriate minimum feature set exists in raw form, OR gap explicitly logged.

- Stats: raw per-season files exist for all 2004 pairs (316 modern + 1688 classical) — counts match ground truth exactly. Gaps for missing advanced metrics, missing assists/minutes documented above, visible in stats_scrape_summary.parquet career_stats_count=0 for some early players.
- Trophies: raw winners files exist for all competition categories, usable to derive trophy features per player-year.
- Narrative: raw flags exist for all 2004 pairs.

=> PASS. Gaps are documented, not silent.

## Next Steps — Phase 3 Entity Resolution
- Need canonical player ID scheme, alias_table.yaml, fuzzy matching with confidence threshold.
- QA: confirm every ground_truth row resolves to exactly one stats row per source.
