"""
Statistical calculations for Fantasy NBA analysis.

Handles z-score calculations, double-double predictions, player statistics
extraction, and team-level aggregations.
"""

import numpy as np
from scipy import stats as scipy_stats

from .constants import STAT_CATEGORIES, STD_DEV_RATIOS
from .players import get_player_per_game_stats


# ============================================================================
# DOUBLE-DOUBLE CALCULATION
# ============================================================================

def calculate_expected_double_doubles(stats_dict):
    """
    Calculate expected double-doubles per game for a player.
    
    Uses normal distribution assumption with global std dev ratios.
    A double-double requires 10+ in at least 2 of: PTS, REB, AST, STL, BLK
    
    Args:
        stats_dict: Dictionary of player's average per-game stats
    
    Returns:
        float: Expected double-doubles per game
    """
    # Stats that can contribute to double-doubles
    dd_stats = ['PTS', 'REB', 'AST', 'STL', 'BLK']
    
    # Calculate probability of 10+ for each stat
    probabilities = []
    for stat in dd_stats:
        avg_value = stats_dict.get(stat)
        if avg_value is None or avg_value == 0:
            probabilities.append(0.0)
            continue
        
        # Calculate standard deviation based on the ratio
        std_dev = avg_value * STD_DEV_RATIOS.get(stat, 0.4)
        
        # Calculate P(X >= 10) using normal distribution
        # P(X >= 10) = 1 - CDF(9.5) (using continuity correction)
        z_score = (9.5 - avg_value) / std_dev if std_dev > 0 else -999
        prob_10_plus = 1 - scipy_stats.norm.cdf(z_score)
        probabilities.append(prob_10_plus)
    
    # Calculate expected double-doubles using combinations
    # P(at least 2 successes) = 1 - P(0) - P(1)
    
    # P(exactly 0 successes)
    p_zero = np.prod([1 - p for p in probabilities])
    
    # P(exactly 1 success)
    p_one = sum(
        probabilities[i] * np.prod([1 - probabilities[j] for j in range(len(probabilities)) if j != i])
        for i in range(len(probabilities))
    )
    
    # P(at least 2) = probability of double-double
    expected_dd = 1 - p_zero - p_one
    
    return expected_dd


# ============================================================================
# STAT EXTRACTION
# ============================================================================

def extract_player_stats(players, year, stats_key):
    """
    Extract statistics for all players for a specific time period.
    
    Args:
        players: List of player objects
        year: Season year
        stats_key: Stats key (e.g., '2026_projected', '2026_total')
    
    Returns:
        tuple: (player_stats dict, raw_stats dict)
    """
    # Dictionary to store raw stats for all players
    raw_stats = {stat: [] for stat in STAT_CATEGORIES}
    
    # Dictionary to store player stats
    player_stats = {}
    
    # Extract stats from each player
    for player in players:
        if not hasattr(player, 'stats') or not player.stats:
            continue
        
        # Try to use the requested stats_key, fallback to projected if not available
        actual_stats_key = stats_key
        if stats_key not in player.stats or 'avg' not in player.stats[stats_key]:
            # Player hasn't played yet, use projected stats
            projected_key = f'{year}_projected'
            if projected_key in player.stats and 'avg' in player.stats[projected_key]:
                actual_stats_key = projected_key
            else:
                continue
        
        player_avg_stats = player.stats[actual_stats_key]['avg']
        player_stats[player] = {}
        
        # Extract each stat category
        for stat in STAT_CATEGORIES:
            if stat == 'DD':
                # DD will be calculated separately
                continue
            
            # Handle 3PM which might be stored as '3PTM'
            if stat == '3PM':
                value = player_avg_stats.get('3PM', player_avg_stats.get('3PTM', None))
            else:
                value = player_avg_stats.get(stat, None)
            
            if value is not None and isinstance(value, (int, float)):
                player_stats[player][stat] = float(value)
                raw_stats[stat].append(float(value))
            else:
                player_stats[player][stat] = None
    
    return player_stats, raw_stats


def add_double_doubles(player_stats, raw_stats):
    """
    Calculate and add expected double-doubles for all players.
    
    Args:
        player_stats: Dictionary mapping players to their stats
        raw_stats: Dictionary of stat lists for calculating means/stds
    """
    for player, stats in player_stats.items():
        expected_dd = calculate_expected_double_doubles(stats)
        player_stats[player]['DD'] = expected_dd
        raw_stats['DD'].append(expected_dd)


# ============================================================================
# Z-SCORE CALCULATION
# ============================================================================

def calculate_player_zscores(players, stats_key='2026_projected'):
    """
    Calculate z-scores for all players to use for ranking.
    
    Args:
        players: List of ESPN Player objects
        stats_key: Stats key to use for per-game averages
    
    Returns:
        dict: Mapping of player name to their z-scores and per_game_power
    """
    # Collect raw stats for all players
    player_stats = {}
    raw_stats = {stat: [] for stat in STAT_CATEGORIES}
    
    for player in players:
        per_game_stats = get_player_per_game_stats(player, stats_key)
        if per_game_stats is None:
            continue
        
        stats = {}
        for stat in STAT_CATEGORIES:
            if stat == 'DD':
                continue
            elif stat == '3PM':
                value = per_game_stats.get('3PM', per_game_stats.get('3PTM'))
            else:
                value = per_game_stats.get(stat)
            
            if value is not None and isinstance(value, (int, float)):
                stats[stat] = float(value)
                raw_stats[stat].append(float(value))
            else:
                stats[stat] = None
        
        # Add DD
        expected_dd = calculate_expected_double_doubles(per_game_stats)
        stats['DD'] = expected_dd
        raw_stats['DD'].append(expected_dd)
        
        player_stats[player.name] = stats
    
    # Calculate mean and std for each stat
    stat_means = {}
    stat_stds = {}
    for stat in STAT_CATEGORIES:
        if len(raw_stats[stat]) > 0:
            stat_means[stat] = np.mean(raw_stats[stat])
            stat_stds[stat] = np.std(raw_stats[stat])
        else:
            stat_means[stat] = 0
            stat_stds[stat] = 1
    
    # Calculate z-scores
    player_zscores = {}
    for player_name, stats in player_stats.items():
        zscores = {}
        for stat in STAT_CATEGORIES:
            if stats[stat] is not None and stat_stds[stat] != 0:
                z_score = (stats[stat] - stat_means[stat]) / stat_stds[stat]
                zscores[stat] = z_score
            else:
                zscores[stat] = 0.0
        
        # Calculate per-game power as sum of z-scores
        per_game_power = sum(zscores.values())
        zscores['per_game_power'] = per_game_power
        player_zscores[player_name] = zscores
    
    return player_zscores


def calculate_zscores(player_stats, raw_stats, year, stats_key):
    """
    Calculate z-scores and power scores for all players.
    
    Args:
        player_stats: Dictionary mapping players to their stats
        raw_stats: Dictionary of stat lists for calculating means/stds
        year: Season year
        stats_key: Stats key for getting games played
    
    Returns:
        dict: Dictionary mapping players to their z-scores and power scores
    """
    # Calculate mean and standard deviation for each stat
    stat_means = {}
    stat_stds = {}
    
    for stat in STAT_CATEGORIES:
        if len(raw_stats[stat]) > 0:
            stat_means[stat] = np.mean(raw_stats[stat])
            stat_stds[stat] = np.std(raw_stats[stat])
        else:
            stat_means[stat] = 0
            stat_stds[stat] = 1
    
    # Calculate z-scores for each player
    player_zscores = {}
    
    # First pass: calculate per_game_power and get games played
    for player, stats in player_stats.items():
        player_zscores[player] = {}
        
        for stat in STAT_CATEGORIES:
            if stats[stat] is not None and stat_stds[stat] != 0:
                z_score = (stats[stat] - stat_means[stat]) / stat_stds[stat]
                player_zscores[player][stat] = z_score
            else:
                player_zscores[player][stat] = 0.0
        
        # Calculate per-game power_score as the sum of all z-scores
        per_game_power = sum(player_zscores[player].values())
        player_zscores[player]['per_game_power'] = per_game_power
        
        # Get games played from projected stats
        gp = 82  # Default to full season
        projected_key = f'{year}_projected'
        if hasattr(player, 'stats') and player.stats:
            if projected_key in player.stats and 'avg' in player.stats[projected_key]:
                gp = player.stats[projected_key]['avg'].get('GP', 82)
        
        player_zscores[player]['games_played'] = gp
    
    # Find the minimum per_game_power to create a baseline
    min_power = min(p['per_game_power'] for p in player_zscores.values())
    baseline = abs(min_power) + 1 if min_power < 0 else 0
    
    # Second pass: calculate season_power with proper handling of negative scores
    for player in player_zscores.values():
        per_game_power = player['per_game_power']
        gp = player['games_played']
        
        # Shift to positive scale, apply GP weight
        adjusted_score = per_game_power + baseline
        player['per_game_power'] = adjusted_score
        player['season_power'] = (adjusted_score * (gp / 82.0))
    
    return player_zscores


# ============================================================================
# TEAM STATISTICS
# ============================================================================

def calculate_team_stats(team_player_zscores):
    """
    Calculate average statistics for each team across all stat categories.
    
    Args:
        team_player_zscores: Dictionary of team -> player -> scores
    
    Returns:
        dict: Dictionary of team -> stat -> average value
    """
    team_stats = {}
    
    for team_name, players in team_player_zscores.items():
        if team_name == "Free Agents":
            continue
        
        if not players:
            continue
        
        team_stats[team_name] = {}
        
        # Calculate average for each stat category
        for stat in STAT_CATEGORIES:
            stat_values = []
            for player_stats in players.values():
                if stat in player_stats and player_stats[stat] is not None:
                    stat_values.append(player_stats[stat])
            
            if stat_values:
                team_stats[team_name][stat] = np.mean(stat_values)
            else:
                team_stats[team_name][stat] = 0.0
        
        # Calculate roster size
        team_stats[team_name]['roster_size'] = len(players)
    
    return team_stats


def build_team_dictionary(league, player_zscores, top_free_agents):
    """
    Organize player z-scores by team.
    
    Args:
        league: ESPN League object
        player_zscores: Dictionary mapping players to their z-scores
        top_free_agents: List of free agent player objects
    
    Returns:
        dict: Dictionary organized by team name
    """
    team_player_zscores = {}
    
    # Add rostered players organized by team
    for team in league.teams:
        team_name = team.team_name
        team_player_zscores[team_name] = {}
        
        for player in team.roster:
            if player in player_zscores:
                player_name = player.name
                team_player_zscores[team_name][player_name] = player_zscores[player]
    
    # Add free agents under a special "Free Agents" category
    team_player_zscores["Free Agents"] = {}
    for player in top_free_agents:
        if player in player_zscores:
            player_name = player.name
            team_player_zscores["Free Agents"][player_name] = player_zscores[player]
    
    return team_player_zscores

