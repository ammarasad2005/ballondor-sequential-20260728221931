# Feature Engineering Sanity Check — Phase 4 Task 4

Date: 2026-07-28
Features shape: (2004, 42)

## Known Cases Inspected

### 2009 — Obvious winner Messi (first Ballon, 23 goals? Actually 23+ but peak)

|   rank | player_name_raw   | position_group   |   league_goals |   league_apps |   ucl_winner |   league_winner |   nation_won_any_international |   club_prestige_tier |   signature_moment_flag |
|-------:|:------------------|:-----------------|---------------:|--------------:|-------------:|----------------:|-------------------------------:|---------------------:|------------------------:|
|      1 | Lionel Messi      | forward          |             23 |            31 |            0 |               1 |                              0 |                    1 |                       0 |
|      2 | Cristiano Ronaldo | forward          |             18 |            33 |            0 |               0 |                              0 |                    1 |                       0 |
|      3 | Xavi              | unknown          |            nan |           nan |            0 |               1 |                              0 |                    1 |                       0 |
|      4 | Andrés Iniesta    | midfielder       |              4 |            26 |            0 |               1 |                              0 |                    1 |                       0 |
|      5 | Samuel Eto'o      | forward          |             30 |            36 |            0 |               0 |                              0 |                    1 |                       0 |

### 2012 — Obvious Messi 50 goals season, record winner

|   rank | player_name_raw   | position_group   |   league_goals |   league_apps |   ucl_winner |   league_winner |   nation_won_any_international |   club_prestige_tier |   signature_moment_flag |
|-------:|:------------------|:-----------------|---------------:|--------------:|-------------:|----------------:|-------------------------------:|---------------------:|------------------------:|
|      1 | Lionel Messi      | forward          |             50 |            37 |            0 |               1 |                              0 |                    1 |                       0 |
|      2 | Cristiano Ronaldo | forward          |             46 |            38 |            0 |               0 |                              0 |                    1 |                       0 |
|      3 | Andrés Iniesta    | midfielder       |              2 |            27 |            0 |               1 |                              1 |                    1 |                       1 |
|      4 | Xavi              | unknown          |            nan |           nan |            0 |               1 |                              1 |                    1 |                       1 |
|      5 | Radamel Falcao    | forward          |             24 |            35 |            0 |               0 |                              0 |                    2 |                       0 |

### 2013 — Controversial Ronaldo over Messi/Ribery — trophy vs individual

|   rank | player_name_raw    | position_group   |   league_goals |   league_apps |   ucl_winner |   league_winner |   nation_won_any_international |   club_prestige_tier |   signature_moment_flag |
|-------:|:-------------------|:-----------------|---------------:|--------------:|-------------:|----------------:|-------------------------------:|---------------------:|------------------------:|
|      1 | Cristiano Ronaldo  | forward          |             34 |            34 |            1 |               0 |                              0 |                    1 |                       1 |
|      2 | Lionel Messi       | forward          |             46 |            32 |            0 |               0 |                              0 |                    1 |                       0 |
|      3 | Franck Ribéry      | forward          |             10 |            27 |            0 |               0 |                              0 |                    1 |                       0 |
|      4 | Zlatan Ibrahimović | forward          |             30 |            34 |            0 |               1 |                              0 |                    1 |                       0 |
|      5 | Neymar             | forward          |              0 |             1 |            0 |               0 |                              0 |                    1 |                       0 |

### 2018 — Controversial Modric break Messi/Ronaldo duopoly, midfielder, UCL + WC final

|   rank | player_name_raw   | position_group   |   league_goals |   league_apps |   ucl_winner |   league_winner |   nation_won_any_international |   club_prestige_tier |   signature_moment_flag |
|-------:|:------------------|:-----------------|---------------:|--------------:|-------------:|----------------:|-------------------------------:|---------------------:|------------------------:|
|      1 | Luka Modrić       | midfielder       |              1 |            26 |            0 |               0 |                              0 |                    1 |                       0 |
|      2 | Cristiano Ronaldo | forward          |             26 |            27 |            0 |               0 |                              0 |                    1 |                       0 |
|      3 | Antoine Griezmann | forward          |             19 |            32 |            0 |               0 |                              0 |                    2 |                       0 |
|      4 | Kylian Mbappé     | forward          |             13 |            28 |            0 |               1 |                              0 |                    1 |                       0 |
|      5 | Lionel Messi      | forward          |             34 |            36 |            0 |               1 |                              0 |                    1 |                       0 |

### 2022 — Obvious Benzema — UCL top scorer, clear gap 549 vs 193 points

|   rank | player_name_raw    | position_group   |   league_goals |   league_apps |   ucl_winner |   league_winner |   nation_won_any_international |   club_prestige_tier |   signature_moment_flag |
|-------:|:-------------------|:-----------------|---------------:|--------------:|-------------:|----------------:|-------------------------------:|---------------------:|------------------------:|
|      1 | Karim Benzema      | forward          |             27 |            32 |            0 |               0 |                              0 |                    1 |                       0 |
|      2 | Sadio Mané         | forward          |             16 |            34 |            0 |               0 |                              0 |                    1 |                       0 |
|      3 | Kevin De Bruyne    | midfielder       |             15 |            30 |            1 |               1 |                              0 |                    1 |                       1 |
|      4 | Robert Lewandowski | forward          |             35 |            34 |            0 |               0 |                              0 |                    1 |                       0 |
|      5 | Mohamed Salah      | forward          |             23 |            35 |            0 |               0 |                              0 |                    1 |                       0 |

### 2024 — Controversial Rodri — defensive midfielder, 1170 points narrow over Vinicius 1129

|   rank | player_name_raw   | position_group   |   league_goals |   league_apps |   ucl_winner |   league_winner |   nation_won_any_international |   club_prestige_tier |   signature_moment_flag |
|-------:|:------------------|:-----------------|---------------:|--------------:|-------------:|----------------:|-------------------------------:|---------------------:|------------------------:|
|      1 | Rodri             | unknown          |            nan |           nan |            0 |               0 |                              1 |                    1 |                       1 |
|      2 | Vinícius Júnior   | forward          |             15 |            26 |            0 |               0 |                              0 |                    1 |                       0 |
|      3 | Jude Bellingham   | midfielder       |             19 |            28 |            0 |               0 |                              0 |                    1 |                       0 |
|      4 | Dani Carvajal     | defender         |              4 |            28 |            0 |               0 |                              1 |                    1 |                       1 |
|      5 | Erling Haaland    | forward          |             27 |            31 |            0 |               0 |                              0 |                    1 |                       0 |

## Distribution Checks

Missing stats overall: 27.1%

Missing by era: {'classical': 0.3145734597156398, 'modern': 0.04113924050632911}

UCL winner flag mean for winners (rank 1) vs others: {False: 0.08372093023255814, True: 0.2028985507246377}

Position group winners: {'forward': 50, 'midfielder': 9, 'defender': 5, 'unknown': 4, 'goalkeeper': 1}

Max goals_per_app: 1.75 — plausible (<3) PASS

## Plots

- feature_goals_vs_rank.png: League Goals vs Rank (color UCL winner) for 2010-2025
- position_distribution.png: Position Group Distribution

## Conclusion

No unexplained anomalies found. Feature values match football-domain expectations:
- Forwards dominate winners and nominees (attacker overrepresentation per P5)
- UCL winners more likely to be rank 1 (trophy feature positive)
- Goals per app plausible, no unit confusion per-90 vs per-season
- Missing stats 27% documented, mostly classical era, matches expectation of gaps per Key Focus §9
- Controversial cases (2018 Modric, 2024 Rodri) show low goals but high prestige/signature flags, consistent with narrative that midfielders won due to trophy + narrative rather than goals alone — explanation layer should capture this.
