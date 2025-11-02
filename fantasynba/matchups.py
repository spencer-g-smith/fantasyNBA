"""
Matchup prediction and lineup optimization for Fantasy NBA.

Handles lineup position eligibility, daily lineup optimization,
team matchup statistics calculation, and head-to-head comparisons.
"""

from .constants import LINEUP_SLOTS, STAT_CATEGORIES, MATCHUP_SCHEDULE_2026
from .players import get_player_per_game_stats, get_players_playing_on_date
from .stats import calculate_expected_double_doubles


# ============================================================================
# POSITION ELIGIBILITY
# ============================================================================

def can_fill_position(player_position, slot_position):
    """
    Check if a player can fill a specific lineup slot.
    
    Args:
        player_position: Player's position (e.g., 'PG', 'SG', 'PG,SG')
        slot_position: Lineup slot (e.g., 'PG', 'G', 'UTIL')
    
    Returns:
        bool: True if player can fill the slot
    """
    if slot_position == 'UTIL':
        return True
    
    # Handle multi-position players (e.g., "PG,SG")
    player_positions = [p.strip() for p in player_position.split(',')]
    
    if slot_position in player_positions:
        return True
    
    # Handle flex positions
    if slot_position == 'G' and any(pos in ['PG', 'SG'] for pos in player_positions):
        return True
    
    if slot_position == 'F' and any(pos in ['SF', 'PF'] for pos in player_positions):
        return True
    
    return False


# ============================================================================
# LINEUP OPTIMIZATION
# ============================================================================

def optimize_lineup(available_players, player_zscores, stats_key='2026_projected'):
    """
    Select the optimal 10-player lineup respecting position constraints.
    
    Args:
        available_players: List of ESPN Player objects available for this day
        player_zscores: Dict mapping player names to their z-scores
        stats_key: Stats key for getting per-game stats
    
    Returns:
        dict: Lineup with slots as keys and (player, stats) tuples as values
    """
    # Sort players by per_game_power (descending)
    players_with_power = []
    for player in available_players:
        if player.name in player_zscores:
            power = player_zscores[player.name]['per_game_power']
            players_with_power.append((player, power))
    
    players_with_power.sort(key=lambda x: x[1], reverse=True)
    
    # Greedy lineup optimization
    lineup = {}
    used_players = set()
    
    for slot in LINEUP_SLOTS:
        filled = False
        for player, power in players_with_power:
            if player.name in used_players:
                continue
            
            player_position = getattr(player, 'position', 'Unknown')
            if can_fill_position(player_position, slot):
                # Get player stats
                per_game_stats = get_player_per_game_stats(player, stats_key)
                if per_game_stats:
                    # Extract stats we need
                    stats = {}
                    for stat in ['PTS', 'AST', 'BLK', 'REB', 'STL', 'FTM', 'FTA']:
                        stats[stat] = per_game_stats.get(stat, 0) or 0
                    
                    stats['3PM'] = per_game_stats.get('3PM', per_game_stats.get('3PTM', 0)) or 0
                    stats['DD'] = calculate_expected_double_doubles(per_game_stats)
                    
                    lineup[slot] = (player, stats)
                    used_players.add(player.name)
                    filled = True
                    break
        
        if not filled:
            lineup[slot] = None  # Empty slot
    
    return lineup


# ============================================================================
# MATCHUP CALCULATION
# ============================================================================

def calculate_team_matchup_stats(team, matchup_id, league, player_zscores, stats_key='2026_projected'):
    """
    Calculate projected stats for a team across all scoring periods in a matchup.
    
    Args:
        team: ESPN Team object
        matchup_id: Matchup ID
        league: ESPN League object
        player_zscores: Pre-calculated z-scores for ranking
        stats_key: Stats key to use
    
    Returns:
        dict: Total stats for the team across the matchup
    """
    scoring_periods = MATCHUP_SCHEDULE_2026.get(matchup_id, [])
    
    # Initialize totals
    totals = {
        'PTS': 0, 'AST': 0, 'BLK': 0, 'REB': 0, 'STL': 0,
        '3PM': 0, 'FTM': 0, 'FTA': 0, 'DD': 0, 'games_played': 0
    }
    
    # Process each scoring period
    for sp_id in scoring_periods:
        # Get players available on this day
        available_players = get_players_playing_on_date(team.roster, sp_id, matchup_id, league)
        
        if not available_players:
            continue
        
        # Optimize lineup for this day
        lineup = optimize_lineup(available_players, player_zscores, stats_key)
        
        # Accumulate stats from lineup
        for slot, entry in lineup.items():
            if entry is not None:
                player, stats = entry
                for stat in ['PTS', 'AST', 'BLK', 'REB', 'STL', '3PM', 'FTM', 'FTA', 'DD']:
                    totals[stat] += stats.get(stat, 0)
                totals['games_played'] += 1
    
    # Calculate FT%
    if totals['FTA'] > 0:
        totals['FT%'] = totals['FTM'] / totals['FTA']
    else:
        totals['FT%'] = 0.0
    
    return totals


# ============================================================================
# TEAM COMPARISON
# ============================================================================

def compare_teams(team_a_name, team_a_stats, team_b_name, team_b_stats):
    """
    Compare two teams and determine category winners.
    
    Args:
        team_a_name: Name of team A
        team_a_stats: Stats dict for team A
        team_b_name: Name of team B
        team_b_stats: Stats dict for team B
    
    Returns:
        tuple: (category_results dict, team_a_wins, team_b_wins)
    """
    category_results = {}
    team_a_wins = 0
    team_b_wins = 0
    
    for stat in STAT_CATEGORIES:
        a_val = team_a_stats.get(stat, 0)
        b_val = team_b_stats.get(stat, 0)
        
        if a_val > b_val:
            category_results[stat] = team_a_name
            team_a_wins += 1
        elif b_val > a_val:
            category_results[stat] = team_b_name
            team_b_wins += 1
        else:
            category_results[stat] = 'TIE'
    
    return category_results, team_a_wins, team_b_wins

