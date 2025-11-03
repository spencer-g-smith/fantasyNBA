"""
Player data fetching and schedule management for Fantasy NBA.

Handles player roster retrieval, schedule lookups, injury status checks,
and filtering players by availability.
"""

from datetime import datetime
from typing import List, Dict, Optional
from espn_api.basketball import League
from espn_api.basketball.constant import PRO_TEAM_MAP

from .constants import MATCHUP_SCHEDULE_2026


# ============================================================================
# PLAYER DATA FETCHING
# ============================================================================

def get_league_players(league, year):
    """
    Fetch all rostered players and top 30 free agents from the league.
    
    Args:
        league: ESPN League object
        year: Season year
    
    Returns:
        tuple: (all_players, all_rostered_players, top_free_agents)
    """
    # Collect all rostered players
    all_rostered_players = []
    for team in league.teams:
        for player in team.roster:
            all_rostered_players.append(player)
    
    # Get top 30 free agents
    top_free_agents = league.free_agents(size=60)
    
    # Combine all players
    all_players = all_rostered_players + top_free_agents
    
    return all_players, all_rostered_players, top_free_agents


def get_player_per_game_stats(player, stats_key='2026_projected'):
    """
    Get per-game average statistics for a player.
    
    Args:
        player: ESPN Player object
        stats_key: Stats key (e.g., '2026_projected', '2026_last_30')
    
    Returns:
        dict: Per-game statistics or None if not available
    """
    if not hasattr(player, 'stats') or not player.stats:
        return None
    
    if stats_key not in player.stats:
        return None
    
    if 'avg' not in player.stats[stats_key] or player.stats[stats_key]['avg'] is None:
        return None
    
    return player.stats[stats_key]['avg']


# ============================================================================
# INJURY STATUS
# ============================================================================

def is_player_injured(player):
    """
    Check if a player is injured and should be excluded from lineup.
    
    Args:
        player: ESPN Player object
    
    Returns:
        bool: True if player is injured (OUT status), False otherwise
    """
    # Check injury status
    injury_status = getattr(player, 'injuryStatus', None)
    
    # Consider player injured if status is 'OUT'
    if injury_status == 'OUT':
        return True
    
    # Also check the 'injured' boolean flag
    injured = getattr(player, 'injured', False)
    if injured:
        return True
    
    return False


# ============================================================================
# SCHEDULE MANAGEMENT
# ============================================================================

def get_player_schedule(player: object, matchup_id: int, league: League) -> List[Dict]:
    """
    Get a player's NBA game schedule for a specific fantasy matchup period.
    
    Args:
        player: The ESPN Player object (from team.roster or league.free_agents())
        matchup_id: The fantasy matchup period ID
        league: The ESPN League object
    
    Returns:
        List of dictionaries with schedule information:
        [
            {
                'date': datetime.date,
                'opponent': str,
                'scoring_period_id': int
            },
            ...
        ]
    
    Example:
        >>> league = League(league_id=123456, year=2026)
        >>> player = league.teams[0].roster[0]
        >>> schedule = get_player_schedule(player, matchup_id=5, league=league)
        >>> for game in schedule:
        ...     print(f"{game['date']}: vs {game['opponent']}")
    """
    pro_team_id = _get_pro_team_id_by_name(player.proTeam)
    if pro_team_id is None:
        return []
    
    scoring_periods = _get_scoring_periods_for_matchup(matchup_id, league)
    if not scoring_periods:
        return []
    
    return _build_schedule(pro_team_id, scoring_periods, league)


def _get_pro_team_id_by_name(team_name: str) -> Optional[int]:
    """Convert NBA team name (e.g., 'LAL', 'BOS') to team ID."""
    for team_id, name in PRO_TEAM_MAP.items():
        if name == team_name:
            return team_id
    return None


def _get_scoring_periods_for_matchup(matchup_id: int, league: League) -> List[int]:
    """Get the list of scoring periods for a matchup ID."""
    return MATCHUP_SCHEDULE_2026.get(matchup_id, [])


def _build_schedule(pro_team_id: int, scoring_periods: List[int], league: League) -> List[Dict]:
    """
    Build schedule from league's pro_schedule data.
    
    Returns:
        List of game dictionaries sorted by date, each containing:
        - date: datetime.date
        - opponent: str (team name)
        - scoring_period_id: int
    """
    if not hasattr(league, 'pro_schedule') or pro_team_id not in league.pro_schedule:
        return []
    
    team_schedule = league.pro_schedule[pro_team_id]
    schedule = []
    
    for period in scoring_periods:
        games = team_schedule.get(str(period), [])
        if not games:
            continue
        
        game = games[0]  # One game per scoring period
        
        # Determine opponent team
        opponent_id = (game['homeProTeamId'] 
                      if game['awayProTeamId'] == pro_team_id 
                      else game['awayProTeamId'])
        
        schedule.append({
            'date': datetime.fromtimestamp(game['date'] / 1000).date(),
            'opponent': PRO_TEAM_MAP.get(opponent_id, 'Unknown'),
            'scoring_period_id': period
        })
    
    return sorted(schedule, key=lambda x: x['date'])


# ============================================================================
# PLAYER FILTERING
# ============================================================================

def get_players_playing_on_date(team_roster, scoring_period_id, matchup_id, league):
    """
    Filter team roster to only players who have a game on the given scoring period
    and are not injured.
    
    Args:
        team_roster: List of ESPN Player objects
        scoring_period_id: Scoring period ID (day)
        matchup_id: Matchup ID
        league: ESPN League object
    
    Returns:
        list: Players who have a game on this date and are not injured
    """
    playing_players = []
    
    for player in team_roster:
        # Skip injured players
        if is_player_injured(player):
            continue
        
        schedule = get_player_schedule(player, matchup_id, league)
        # Check if player has a game on this scoring period
        for game in schedule:
            if game['scoring_period_id'] == scoring_period_id:
                playing_players.append(player)
                break
    
    return playing_players

