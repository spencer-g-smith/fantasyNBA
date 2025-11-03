"""
Fantasy NBA Library

A library for analyzing ESPN Fantasy Basketball leagues with z-score calculations,
matchup predictions, and lineup optimization.

Example usage:
    from fantasynba import get_league_players, calculate_player_zscores
    from espn_api.basketball import League
    
    league = League(league_id=YOUR_LEAGUE_ID, year=2026)
    players, rostered, free_agents = get_league_players(league, 2026)
    zscores = calculate_player_zscores(players, '2026_projected')
"""

# Import key functions for easy access
from .constants import (
    LEAGUE_ID,
    YEAR,
    STAT_CATEGORIES,
    STD_DEV_RATIOS,
    LINEUP_SLOTS,
    MATCHUP_SCHEDULE_2026,
)

from .players import (
    get_league_players,
    get_player_per_game_stats,
    get_player_schedule,
    is_player_injured,
    get_players_playing_on_date,
)

from .stats import (
    calculate_expected_double_doubles,
    extract_player_stats,
    add_double_doubles,
    calculate_player_zscores,
    calculate_zscores,
    calculate_team_stats,
    build_team_dictionary,
)

from .matchups import (
    can_fill_position,
    optimize_lineup,
    calculate_team_matchup_stats,
    compare_teams,
)

from .display import (
    display_player_scores,
    display_team_rankings,
    display_team_statistics,
    display_stat_rankings,
    display_overall_rankings,
    display_matchup_results,
)

from .utils import (
    convert_stat_key,
    fuzzy_find_player,
    get_current_matchup_id,
    fuzzy_find_team,
)

__version__ = "1.0.0"
__all__ = [
    # Constants
    "LEAGUE_ID",
    "YEAR",
    "STAT_CATEGORIES",
    "STD_DEV_RATIOS",
    "LINEUP_SLOTS",
    "MATCHUP_SCHEDULE_2026",
    # Players
    "get_league_players",
    "get_player_per_game_stats",
    "get_player_schedule",
    "is_player_injured",
    "get_players_playing_on_date",
    # Stats
    "calculate_expected_double_doubles",
    "extract_player_stats",
    "add_double_doubles",
    "calculate_player_zscores",
    "calculate_zscores",
    "calculate_team_stats",
    "build_team_dictionary",
    # Matchups
    "can_fill_position",
    "optimize_lineup",
    "calculate_team_matchup_stats",
    "compare_teams",
    # Display
    "display_player_scores",
    "display_team_rankings",
    "display_team_statistics",
    "display_stat_rankings",
    "display_overall_rankings",
    "display_matchup_results",
    # Utils
    "convert_stat_key",
    "fuzzy_find_player",
    "get_current_matchup_id",
    "fuzzy_find_team",
]

