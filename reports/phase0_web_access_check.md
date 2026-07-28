# Phase 0 Web Access Check — 2026-07-28

## Test Results

### Ground Truth Category
- https://en.wikipedia.org/wiki/Ballon_d%27Or -> 200 OK, 1,378,846 bytes, 9 wikitable tables detected
- https://en.wikipedia.org/wiki/2023_Ballon_d%27Or -> 200 OK, 708,115 bytes, 9 wikitable tables, first table headers: ['Rank','Player','Nationality','Position','Club'] — IDEAL for scraping
- https://en.wikipedia.org/wiki/2024_Ballon_d%27Or -> 200 OK
- https://en.wikipedia.org/wiki/2015_FIFA_Ballon_d%27Or -> 200 OK
- https://www.francefootball.fr/ballon-d-or/ -> 200 OK, 200,181 bytes — accessible as secondary verification source
- https://en.wikipedia.org/wiki/List_of_Ballon_d%27Or_winners -> 404 (page moved/renamed). Alternative ground truth list page: https://en.wikipedia.org/wiki/Ballon_d%27Or table itself contains historical winners list.
- Verdict: PASS — Wikipedia year pages are well-structured and reliable primary source.

### Trophy / Competition Category
- https://en.wikipedia.org/wiki/List_of_European_Cup_and_UEFA_Champions_League_finals -> 200 OK, 604,619 bytes
- https://en.wikipedia.org/wiki/List_of_FIFA_World_Cup_finals -> 200 OK, 425,802 bytes
- Verdict: PASS — both UCL and World Cup finals tables accessible.

### Individual Stats Category
- https://fbref.com/en/players/dea698d9/Lionel-Messi -> 403 Forbidden via requests, 403 via spoofed Chrome UA. Via Playwright Chromium -> returns Cloudflare "Just a moment..." challenge page (27,418 bytes) — indicates Cloudflare bot protection in front of FBref.
- https://en.wikipedia.org/wiki/Lionel_Messi -> 200 OK, 3,125,090 bytes — player page contains career stats tables, fallback for goals/appearances
- Attempted FBRef league stats https://fbref.com/en/comps/9/Premier-League-Stats -> same 403.
- Verdict: PARTIAL PASS — FBRef advanced metrics (xG, progressive actions) blocked by Cloudflare/Akamai WAF. This matches Requirements B.2 note that reserve headless browser may be needed, but even Playwright hits Cloudflare challenge. Mitigations for Phase 2:
  - Option A: Use Wikipedia player season stats (goals, assists, appearances) as primary for both eras, document advanced metrics as best-effort gap per Key Focus Area §9 (visible not silent).
  - Option B: Seek alternative open sources that may not be Cloudflare-protected: worldfootball.net, espn.com, or transfermarkt player stats pages. Need to test those.
  - Option C: Explore fbref's sister site stats via statsdump or via API? Possibly use https API with delay and proper referer? But given WAF, likely still blocked; may need undetected_chromedriver or more sophisticated bypass, or accept gap.
  - Decision for Phase 0 exit: stats category considered accessible via Wikipedia fallback, but advanced metrics gap is now a known risk flagged for Phase 2. This is logged as transparent gap per P5/P6.

## Additional Technical Checks
- Python 3.13.14
- Libraries verified:
  - requests 2.33.0 OK
  - httpx 0.28.1 OK
  - bs4 4.15.0 OK
  - pandas 2.2.3 OK
  - pyarrow 25.0.0 installed now
  - pyyaml 6.0.3 OK
  - rapidfuzz 3.14.5 installed now
  - scikit-learn 1.6.1 OK
  - xgboost 3.3.0 installed now
  - lightgbm 4.7.0 installed now
  - shap 0.52.0 installed now
  - scipy 1.17.1 OK
  - matplotlib 3.10.9 OK
- Playwright installed + Chromium 149.0.7827.55 — but still blocked by Cloudflare on FBRef.

## Conclusion
Exit criterion for Phase 0: Repo skeleton exists yes, run_config.yaml populated yes, test-fetch at least one page per category yes (ground truth PASS, trophies PASS, stats PARTIAL PASS via Wikipedia fallback). Overall Phase 0 EXIT MET with flagged risk for modern advanced metrics source.

Next: Phase 1 Ground Truth Backbone.
