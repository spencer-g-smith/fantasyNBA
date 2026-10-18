"""
Player data fetching and schedule management for Fantasy NBA.

Handles player roster retrieval, schedule lookups, injury status checks,
and filtering players by availability.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from espn_api.basketball import League
from espn_api.basketball.constant import PRO_TEAM_MAP, STATS_MAP
from espn_api.basketball.player import Player

from .constants import get_matchup_schedule, YEAR


# ============================================================================
# PLAYER DATA FETCHING
# ============================================================================

def comparison_pool_ids(year=YEAR):
    """Versioned membership, independent of current availability or ownership."""
    path = Path(__file__).resolve().parent.parent / 'data' / f'comparison_pool_{year}.json'
    data = json.loads(path.read_text())
    ids = [row['id'] for row in data['players']]
    if len(ids) != 100 or len(set(ids)) != 100 or data['year'] != year:
        raise ValueError('Comparison pool must contain exactly 100 unique player IDs')
    return ids


def get_comparison_players(players, year=YEAR):
    ids = comparison_pool_ids(year)
    lookup = {p.playerId: p for p in players}
    missing = set(ids) - lookup.keys()
    if missing:
        raise ValueError(f'Missing {len(missing)} fixed comparison-pool players; fetch get_league_players first')
    return [lookup[player_id] for player_id in ids]


def attach_espn_records(player, entry):
    """Keep observed historical splits discarded by espn-api 0.45.1.

    Source 0 = observed; source 1 = projection; split 0 = full season.
    averageStats is already per game, except GP which is a season game count.
    """
    for split in entry['player'].get('stats', []):
        source = split.get('statSourceId')
        if source not in (0, 1) or split.get('statSplitTypeId') != 0:
            continue
        season = split['seasonId']
        key = f"{season}_{'total' if source == 0 else 'projected'}"
        total = {STATS_MAP.get(k, k): v for k, v in split.get('stats', {}).items()}
        avg = {STATS_MAP.get(k, k): v for k, v in split.get('averageStats', {}).items()}
        if not avg and total.get('GP', 0) > 0:
            # Only derive explicitly known counts, never divide ratios or GP.
            avg = {k: total[k] / total['GP'] for k in ('PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', '3PTM', 'FTM', 'FTA', 'DD') if k in total}
            avg['GP'] = total['GP']
            if 'FTM' in total and total.get('FTA', 0) > 0:
                avg['FT%'] = total['FTM'] / total['FTA']
        player.stats[key] = {'avg': avg, 'total': total, 'source_id': source,
                             'season_id': season, 'split_type_id': 0}
    return player


def get_league_players(league, year):
    """Fetch roster/availability plus every frozen pool member and raw history."""
    rostered = [p for team in league.teams for p in team.roster]
    free_agents = league.free_agents(size=100)
    players = {p.playerId: p for p in rostered + free_agents}
    ids = list(dict.fromkeys(comparison_pool_ids(year) + list(players)))
    # ESPN rejects combining filterIds and limit on this view.
    filters = {'players': {'filterIds': {'value': ids}}}
    data = league.espn_request.league_get(
        params={'view': 'kona_player_info'},
        headers={'x-fantasy-filter': json.dumps(filters)})
    for entry in data.get('players', []):
        player_id = entry['player']['id']
        player = players.get(player_id)
        if player is None:
            player = Player(entry, year)
            players[player_id] = player
        attach_espn_records(player, entry)
    # Fail visibly if ESPN drops a reference player, rather than shrinking pool.
    get_comparison_players(list(players.values()), year)
    return list(players.values()), rostered, free_agents


def get_player_per_game_stats(player, stats_key=f'{YEAR}_projected'):
    """
    Get per-game average statistics for a player.
    
    Args:
        player: ESPN Player object
        stats_key: Stats key (e.g., '2027_projected', '2027_last_30')
    
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
        >>> league = League(league_id=123456, year=2027)
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
    return get_matchup_schedule(league).get(matchup_id, [])


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

