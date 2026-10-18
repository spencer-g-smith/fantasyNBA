# FT and double-double scoring

Active league: **682068465**, ESPN season **2027** (2026–27). Six teams × 14 spots = 84; the draft comparison pool contains exactly 100 players. Its IDs are versioned in `data/comparison_pool_2027.json`. Membership does not change with draft status, waivers, roster membership, input ordering, or newly available players. Fetching includes all reference players even after they are drafted. Projection values can still change when ESPN updates them. Only pool membership is stored locally; scoring inputs are fetched live.

The initial pool preserves the existing ESPN free-agent query's selection: percent-owned descending with STANDARD draft rank as a secondary sort. The old README called this “ESPN-ranked”; it was not a pure draft-rank sort. Replacing this membership requires an explicit update to the pool definition.

## Verified sources and units

Inspected the actual `kona_player_info` response for this league and the installed **espn-api 0.45.1** parser before changing calculations. Relevant ESPN stat IDs are **15 FTM**, **16 FTA**, **17 3PM**, **20 FT%**, **37 DD**, **38 TD**, **42 GP**. ESPN `statSourceId=0` is observed, `1` is projected; `statSplitTypeId=0` is the full-season split. `stats` contains counting totals; `averageStats` contains per-game counting values. GP remains a game count in both containers. Percentages are fractions between 0 and 1.

- [ESPN league source](https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/2027/segments/0/leagues/682068465?view=kona_player_info)
- [espn-api field mapping](https://github.com/cwendt94/espn-api/blob/master/espn_api/basketball/constant.py), [player parser](https://github.com/cwendt94/espn-api/blob/master/espn_api/basketball/player.py), and [request/filter implementation](https://github.com/cwendt94/espn-api/blob/master/espn_api/requests/espn_requests.py). The pinned installed version was also checked locally; upstream master can change.
- [NBA glossary](https://www.nba.com/stats/help/glossary): DD is a game reaching double figures in two of the five counting categories. This implementation consumes ESPN's DD event count directly; it never substitutes TD, adds TD to DD, or counts each qualifying pair separately.

The Python wrapper discards seasons other than the requested year. `attach_espn_records` preserves raw observed prior-season records for DD history, keeping source/season metadata. Missing `averageStats` can be derived from known counting totals and positive GP. Ratios and GP themselves are never divided by GP.

## Free throws

For projections, `baseline = sum(projected season FTM) / sum(projected season FTA)` over all 100 reference players. This includes their projected games. If ESPN omits both totals, derive them as per-game values × known GP; never assume 82 games. Other requested periods use that period's totals over the same fixed membership.

`FT impact/game = FTM/game − baseline × FTA/game`

`FT impact z = (impact − pool mean impact) / population standard deviation of impact`

Raw FT% and FTA/game remain available separately from **FT impact**. A valid zero-attempt line has zero impact and undefined raw percentage. Missing attempts remain missing. An incomplete reference FT line makes the baseline unavailable; the pool is never silently shrunk. Team and matchup FT% always equal combined makes / combined attempts, with undefined or incomplete results reported as unavailable.

## Double-doubles

Selection order:

1. **Requested observed period:** use `total DD / GP`; if only per-game DD is available, use it once. Require positive GP, a rate in [0,1], and consistency between average and total when both exist. Missing history never falls back to a projection presented as observed.
2. **Explicit ESPN projection:** use validated projected DD totals/GP or the validated per-game DD field. An explicit zero is valid. TD is ignored. If ESPN omits projected DD, continue to the estimates below.
3. **Estimated historical adjustment:** use the latest valid observed season within the previous three years and an empirical prior from comparable historical production lines in the fixed pool. Peers require at least 20 observed games. Compare PTS, REB, AST, STL and BLK using scales (5, 2, 2, 0.75, 0.75); distance is the root mean square of the five scaled differences. Keep up to 8 nearest peers within distance 1.5, require at least 5, exclude the player, and weight each by `min(GP,82)/(0.25+distance)^2`.

   Let `H` be the player's observed DD/GP and `P(old)`, `P(new)` the weighted peer rates at historical and projected production. Then `estimate = clip[0,1](GP/(GP+20) × H + 20/(GP+20) × P(old) + P(new) − P(old))`.

4. **Unique veteran with insufficient peers:** carry forward their own observed DD/GP only with at least 20 historical games and every projected counting stat within `max(0.5/game,20% of historical value)` of history. Label `estimated_history_stable_production`; this assumes the DD rate stays stable within that role range. Otherwise leave DD missing.
5. **Rookie or no usable NBA history:** use the empirical peer rate at projected production only if the same minimum peer requirements pass. Label `estimated_peers_no_history`; identify the missing history explicitly. No assumptions about college-to-NBA conversion or an observed zero are made. The available source does not distinguish a rookie from a veteran whose NBA history is unavailable, so the label says both possibilities.

These estimates use observed joint DD events instead of multiplying independent marginal normal probabilities. They assume similar projected production implies similar DD opportunities. Role changes, injuries, age, stat correlations, and game-to-game variance may still differ. The distance scales, neighborhood limits, and 20 pseudo-games are transparent heuristic choices, not tuned or out-of-sample validated parameters. Stable-role carry-forward is deliberately conservative and does not capture modest improvements in a unique player's production. No current-season DD accuracy claim can be verified before games are played.

## Consistency and missing data

All active ranking and CLI paths use the same extractor, FT baseline, DD resolver, population standard deviation (`ddof=0`), and unshifted per-game power sum. The legacy CLI's artificial positive power shift has been removed so the scores match the connector and lineup rankings; season power is the same sum × projected GP / 82, unavailable if GP is missing. The six other category formulas and all their z-scores remain unchanged, including the existing neutral zero contribution for a missing input. Raw missing values and completeness flags still expose those gaps and make the overall score incomplete. FT/DD missing contributions themselves remain None.

Scoring keys are PTS, REB, AST, STL, BLK, 3PM, **FT impact**, DD. League matchup categories still include **FT%**, because the matchup is decided by the team percentage. Player metadata includes raw statistics, DD source/reason, comparison-pool size, DD reference count, partial power, missing contributions, and `score_complete`. An incomplete overall score is `None`; complete rankings put those players last. DD standardization uses available DD rates in the fixed pool; `dd_reference_count` reports the number of valid rates. The universe stays fixed, while data availability can change.

Lineup ranking uses complete power first, then explicitly provisional partial power. Matchup totals propagate missing FT/DD, return their source metadata, and do not award a category with unavailable inputs. Lineup completeness is included in the result. Three UTIL entries now have distinct keys so all ten selected starters contribute; the previous dictionary overwrote the first two UTIL entries.

If a player lacks a defensible DD estimate or a projected category, the overall score is incomplete; missing fields are not asserted to be zero. When ESPN has not published daily matchup scoring periods, matchup projections report an unavailable schedule. Matchup arithmetic is validated with schedule fixtures.

## Validation

Run from the repository with the dependencies in `requirements.txt` installed:

```bash
python -m unittest discover -s tests -v
```

Tests use small synthetic inputs and generated fixtures covering the fixed pool. They verify FT attempt weighting, DD source selection, missing-input behavior, population z-scores for the six counting categories, consistent connector and CLI scoring, and matchup arithmetic. No captured ESPN statistics or generated reports are required. The deprecated DD library entry point rejects production-only requests and directs callers to the source-aware resolver.
