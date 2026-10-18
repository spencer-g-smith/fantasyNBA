# Fantasy NBA Analysis

A comprehensive Python library and toolkit for analyzing ESPN Fantasy Basketball leagues using z-score calculations, matchup predictions, and lineup optimization.

## Features

- **Real-time Z-Score Analysis** - Calculate player and team power rankings using normalized statistics
- **Team Statistics** - Compare team performance across all statistical categories
- **Matchup Predictions** - Project head-to-head matchup outcomes with optimized daily lineups
- **Lineup Optimization** - Automatically select the best available players respecting position constraints
- **Multiple Time Periods** - Analyze using total season, last 30/15/7 games, or projected stats

## Project Structure

```
fantasynba/                 # Core library package
├── __init__.py            # Package initialization
├── constants.py           # Configuration and league settings
├── players.py             # Player data fetching and schedule management
├── stats.py               # Z-score and statistical calculations
├── matchups.py            # Matchup prediction and lineup optimization
└── display.py             # Display formatting utilities

display_results.py         # Script: Player scores and team rankings
display_team_stats.py      # Script: Team statistics by category
project_matchup_scores.py  # Script: Matchup projections

archive/                   # Archived notebooks and old code
requirements.txt           # Python dependencies
README.md                  # This file
```

## Installation

1. **Clone or download this repository**

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your league**
   
   Edit `fantasynba/constants.py` to set your ESPN league ID and year:
   ```python
   LEAGUE_ID = 682068465  # Your league ID
   YEAR = 2027            # 2026–27 season (ESPN uses the ending year)
   ```

## Usage

### Display Player Scores and Team Rankings

Calculate and display z-scores for all players organized by team:

```bash
# Use last 30 games (default)
python display_results.py

# Use different time periods
python display_results.py --period total
python display_results.py --period projected
python display_results.py --period last_15
python display_results.py --period last_7
```

**Output:**
- Player power scores by team (per-game and season-adjusted)
- Top free agents available
- Team power rankings (normalized by roster size)

### Display Team Statistics

View team-level averages for each statistical category:

```bash
# Show projected stats sorted by team name (default)
python display_team_stats.py

# Sort by specific stat
python display_team_stats.py --sort PTS
python display_team_stats.py --sort overall

# Show detailed category rankings
python display_team_stats.py --show-rankings

# Combine options
python display_team_stats.py --period last_30 --sort REB --show-rankings
```

**Output:**
- Team averages for PTS, BLK, STL, AST, REB, 3PM, FT%, DD
- Summary statistics
- Optional: Detailed rankings by category

### Project Matchup Scores

Predict head-to-head matchup outcomes with optimized lineups:

```bash
# Project matchup 3 using projected stats
python project_matchup_scores.py 3

# Use different stats period
python project_matchup_scores.py 5 --period last_7
python project_matchup_scores.py 12 --period last_30
```

**Output:**
- Category-by-category comparison
- Winner for each statistical category
- Final projected score (e.g., 5-3)

### Available Time Periods

- `total` - Full season statistics
- `last_30` - Last 30 games
- `last_15` - Last 15 games
- `last_7` - Last 7 games
- `projected` - ESPN projected stats (default for some scripts)

## Using the Library

You can also import and use the `fantasynba` package in your own scripts:

```python
from fantasynba import (
    LEAGUE_ID, YEAR,
    get_league_players,
    calculate_player_zscores,
    calculate_team_stats,
    display_player_scores,
)
from espn_api.basketball import League

# Connect to your league
league = League(league_id=LEAGUE_ID, year=YEAR)

# Fetch players
all_players, rostered, free_agents = get_league_players(league, YEAR)

# Calculate z-scores
player_zscores = calculate_player_zscores(all_players, '2027_projected')

# Use the results
print(f"Top player: {max(player_zscores.items(), key=lambda x: x[1]['per_game_power'])}")
```

### Key Library Functions

**Player Management** (`fantasynba.players`)
- `get_league_players(league, year)` - Fetch all players
- `get_player_per_game_stats(player, stats_key)` - Get player averages
- `get_player_schedule(player, matchup_id, league)` - Get game schedule
- `is_player_injured(player)` - Check injury status

**Statistical Calculations** (`fantasynba.stats`)
- `resolve_double_doubles(player, stats_key, peers)` in `fantasynba.scoring` - DD rate with source metadata
- `calculate_player_zscores(players, stats_key)` - Calculate z-scores
- `calculate_team_stats(team_player_zscores)` - Aggregate team stats
- `build_team_dictionary(league, player_zscores, free_agents)` - Organize by team

**Matchup Analysis** (`fantasynba.matchups`)
- `optimize_lineup(available_players, player_zscores, stats_key)` - Daily lineup optimization
- `calculate_team_matchup_stats(team, matchup_id, league, zscores, stats_key)` - Project matchup
- `compare_teams(team_a_name, team_a_stats, team_b_name, team_b_stats)` - Head-to-head

**Display Functions** (`fantasynba.display`)
- `display_player_scores(team_player_zscores, league_teams)` - Format player scores
- `display_team_rankings(team_player_zscores)` - Format team rankings
- `display_team_statistics(team_stats, sort_by)` - Format stat tables
- `display_matchup_results(matchup_id, team_a, stats_a, team_b, stats_b)` - Format matchup

## How It Works

### Z-Score Calculation

The library calculates z-scores for each statistical category (PTS, BLK, STL, AST, REB, 3PM, FT impact, DD) to normalize performance across different scales:

1. **Collect raw stats** for all players
2. **Calculate mean and standard deviation** for each stat
3. **Compute z-score**: `(player_stat - mean) / std_dev`
4. **Sum z-scores** to get per-game power score
5. **Adjust for games played** to get season power score

### FT impact and double-doubles

FT scoring uses attempt-weighted **FT impact**: per-game FTM minus the fixed pool's combined FTM/FTA baseline × per-game FTA. Raw FT% and FTA/game remain separate. DD uses actual DD/GP for observed periods, a validated explicit projection when available, or source-labeled historical/production estimates. Missing contributions produce an incomplete overall score.

See [sources, formulas, assumptions and validation](docs/scoring.md).

### Lineup Optimization

For matchup predictions, lineups are optimized daily:

1. **Filter available players** (not injured, have game that day)
2. **Calculate z-scores** for ranking
3. **Greedy optimization** - fill position slots with highest-ranked eligible players
4. **Position constraints**: PG, SG, SF, PF, C, G, F, 3×UTIL
5. **Aggregate stats** across all days in the matchup period

## Configuration

Edit `fantasynba/constants.py` to customize:

- **League settings**: `LEAGUE_ID`, `YEAR`
- **Stat categories**: `STAT_CATEGORIES`
- **Frozen draft pool**: `data/comparison_pool_2027.json` (100 IDs)
- **Lineup structure**: `LINEUP_SLOTS`
- **Matchup schedule**: `get_matchup_schedule(league)` reads current ESPN daily scoring periods

## Requirements

- Python 3.8+
- espn-api >= 0.37.0
- numpy >= 1.24.0
- scipy >= 1.10.0

## Notes

- Calculations refresh ESPN inputs in real time; only the fixed comparison-pool membership is stored locally
- Requires active ESPN Fantasy Basketball league access
- API calls may take a few seconds depending on league size
- Double-double projections distinguish explicit sources, documented estimates, and missing values

## License

This project is for personal use in analyzing fantasy basketball leagues.

## Author

Spencer Smith


### 2026–27 season

The active season is `YEAR = 2027`, using ESPN’s ending-year convention. Projection defaults use `2027_projected`. Matchup projections use ESPN’s daily scoring periods and report an unavailable schedule explicitly during preseason rather than reusing last season’s dates. The connected hosted MCP service needs these changes deployed before it returns the updated season; local changes do not update the hosted service.

Draft preparation uses a fixed 100-player comparison pool (84 roster spots across six teams, plus 16 additional candidates). Membership is saved before drafting and includes drafted players when calculating baselines. All scoring paths use that same pool; availability only filters the displayed free agents. See the scoring documentation for the initial ESPN selection order.
