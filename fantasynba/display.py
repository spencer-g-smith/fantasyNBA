"""
Display and formatting utilities for Fantasy NBA analysis.

Handles all console output formatting for player scores, team rankings,
statistics tables, and matchup results.
"""

import numpy as np

from .constants import STAT_CATEGORIES
from .matchups import compare_teams
from .stats import SCORING_CATEGORIES, power_sort_key


def fmt(value, digits=3):
    return "N/A" if value is None else f"{value:.{digits}f}"


def average_complete(values):
    return float(np.mean(values)) if values and all(v is not None for v in values) else None


def sortable(value):
    return value is not None, value or 0


# ============================================================================
# PLAYER DISPLAY FUNCTIONS
# ============================================================================

def display_player_scores(team_player_zscores, league_teams):
    """
    Display player power scores organized by team.
    
    Args:
        team_player_zscores: Dictionary of team -> player -> scores
        league_teams: List of ESPN team objects
    """
    print("\n" + "=" * 80)
    print("PLAYER POWER SCORES BY TEAM")
    print("=" * 80)
    
    # Display each team's players sorted by season power score
    for team in league_teams:
        team_name = team.team_name
        if team_name not in team_player_zscores:
            continue
        
        print(f"\n{team_name}")
        print("-" * 80)
        
        # Sort players by season_power (descending)
        sorted_players = sorted(
            team_player_zscores[team_name].items(),
            key=lambda x: power_sort_key(x[1], 'season_power'),
            reverse=True
        )
        
        print(f"{'Player':<30} {'GP':>6} {'Per-Game':>12} {'Season':>12} {'FT%':>8} {'FTA/g':>8} {'FT impact z':>12} {'DD/g':>8} DD source")
        print("-" * 80)
        for player_name, stats in sorted_players:
            print(f"{player_name:<30} {fmt(stats['games_played'], 0):>6} "
                  f"{fmt(stats['per_game_power'], 2):>12} {fmt(stats['season_power'], 2):>12} "
                  f"{fmt(stats['raw_stats']['FT%']):>8} {fmt(stats['raw_stats']['FTA']):>8} "
                  f"{fmt(stats['FT impact']):>12} {fmt(stats['raw_stats']['DD']):>8} {stats['dd']['source']}")
            if not stats['score_complete']:
                print('  Incomplete score: ' + ', '.join(stats['missing_contributions']))
    
    # Display top free agents
    if "Free Agents" in team_player_zscores:
        print(f"\nTop Free Agents")
        print("-" * 80)
        
        # Sort free agents by season_power (descending)
        sorted_fa = sorted(
            team_player_zscores["Free Agents"].items(),
            key=lambda x: power_sort_key(x[1], 'season_power'),
            reverse=True
        )
        
        print(f"{'Player':<30} {'GP':>6} {'Per-Game':>12} {'Season':>12} {'FT%':>8} {'FTA/g':>8} {'FT impact z':>12} {'DD/g':>8} DD source")
        print("-" * 80)
        for player_name, stats in sorted_fa:
            print(f"{player_name:<30} {fmt(stats['games_played'], 0):>6} "
                  f"{fmt(stats['per_game_power'], 2):>12} {fmt(stats['season_power'], 2):>12} "
                  f"{fmt(stats['raw_stats']['FT%']):>8} {fmt(stats['raw_stats']['FTA']):>8} "
                  f"{fmt(stats['FT impact']):>12} {fmt(stats['raw_stats']['DD']):>8} {stats['dd']['source']}")
            if not stats['score_complete']:
                print('  Incomplete score: ' + ', '.join(stats['missing_contributions']))


def display_team_rankings(team_player_zscores):
    """
    Display team power rankings.
    
    Args:
        team_player_zscores: Dictionary of team -> player -> scores
    """
    print("\n" + "=" * 80)
    print("TEAM POWER RANKINGS")
    print("=" * 80)
    
    # Calculate normalized power scores for each team
    team_scores = {}
    for team_name, players in team_player_zscores.items():
        if team_name == "Free Agents":
            continue
        
        roster_size = len(players)
        if roster_size == 0:
            continue
            
        season_average = average_complete([player['season_power'] for player in players.values()])
        per_game_average = average_complete([player['per_game_power'] for player in players.values()])
        
        team_scores[team_name] = {
            'season_score': season_average,
            'per_game_score': per_game_average,
            'roster_size': roster_size
        }
    
    # Sort teams by normalized season score (descending)
    sorted_teams = sorted(team_scores.items(), key=lambda x: sortable(x[1]['season_score']), reverse=True)
    
    # Print rankings
    print(f"\n{'Rank':<6} {'Team Name':<35} {'Avg Season':>15} {'Avg Per-Game':>15} {'Roster':>10}")
    print("-" * 90)
    
    for rank, (team_name, stats) in enumerate(sorted_teams, 1):
        print(f"{rank:<6} {team_name:<35} {fmt(stats['season_score'], 2):>15} "
              f"{fmt(stats['per_game_score'], 2):>15} {stats['roster_size']:>10}")
    
    print("\n" + "=" * 80)


# ============================================================================
# TEAM STATISTICS DISPLAY FUNCTIONS
# ============================================================================

def display_team_statistics(team_stats, sort_by='name'):
    """
    Display team statistics in a formatted table.
    
    Args:
        team_stats: Dictionary of team -> stat -> average value
        sort_by: How to sort teams ('name' or a stat category)
    """
    print("\n" + "=" * 120)
    print("TEAM STATISTICS - AVERAGE Z-SCORES BY CATEGORY (FT impact replaces FT%)")
    print("=" * 120)
    
    # Header
    header = f"{'Team Name':<30}"
    for stat in SCORING_CATEGORIES:
        header += f"{stat:>10}"
    header += f"{'Raw FT%':>10}{'FTA':>10}{'Roster':>10}"
    print(header)
    print("=" * 120)
    
    # Sort teams
    if sort_by == 'name':
        sorted_teams = sorted(team_stats.items(), key=lambda x: x[0])
    elif sort_by == 'overall':
        # Sort by average across all stats
        sorted_teams = sorted(
            team_stats.items(),
            key=lambda x: sortable(average_complete([x[1][stat] for stat in SCORING_CATEGORIES])),
            reverse=True
        )
    else:
        # Sort by specific stat
        sorted_teams = sorted(
            team_stats.items(),
            key=lambda x: sortable(x[1].get(sort_by)),
            reverse=True
        )
    
    # Display each team's stats
    for team_name, stats in sorted_teams:
        row = f"{team_name:<30}"
        for stat in SCORING_CATEGORIES:
            value = stats[stat]
            row += f"{fmt(value):>10}"
        row += f"{fmt(stats['FT%']):>10}{fmt(stats['FTA']):>10}{stats['roster_size']:>10}"
        print(row)
    
    print("=" * 120)
    
    # Print summary statistics
    print("\nSummary:")
    print(f"  Teams: {len(team_stats)}")
    print(f"  Total Roster Spots: {sum(s['roster_size'] for s in team_stats.values())}")
    print(f"  Average Roster Size: {np.mean([s['roster_size'] for s in team_stats.values()]):.1f}")


def display_stat_rankings(team_stats):
    """
    Display rankings for each individual stat category.
    
    Args:
        team_stats: Dictionary of team -> stat -> average value
    """
    print("\n" + "=" * 80)
    print("CATEGORY RANKINGS")
    print("=" * 80)
    
    for stat in SCORING_CATEGORIES:
        print(f"\n{stat} Rankings:")
        print("-" * 80)
        
        # Sort teams by this stat (descending)
        sorted_teams = sorted(
            team_stats.items(),
            key=lambda x: sortable(x[1][stat]),
            reverse=True
        )
        
        print(f"{'Rank':<6} {'Team Name':<35} {'Average':>15}")
        print("-" * 80)
        
        for rank, (team_name, stats) in enumerate(sorted_teams, 1):
            print(f"{rank:<6} {team_name:<35} {fmt(stats[stat]):>15}")


def display_overall_rankings(team_stats):
    """
    Display overall team rankings based on average z-score across all categories.
    
    Args:
        team_stats: Dictionary of team -> stat -> average value
    """
    print("\n" + "=" * 80)
    print("OVERALL TEAM RANKINGS (Average Z-Score Across All Categories)")
    print("=" * 80)
    
    # Calculate overall average for each team
    team_overall = {}
    for team_name, stats in team_stats.items():
        stat_values = [stats[stat] for stat in SCORING_CATEGORIES]
        team_overall[team_name] = average_complete(stat_values)
    
    # Sort by overall average (descending)
    sorted_teams = sorted(
        team_overall.items(),
        key=lambda x: sortable(x[1]),
        reverse=True
    )
    
    print(f"{'Rank':<6} {'Team Name':<35} {'Avg Z-Score':>15} {'Roster':>10}")
    print("-" * 80)
    
    for rank, (team_name, avg_score) in enumerate(sorted_teams, 1):
        roster_size = team_stats[team_name]['roster_size']
        print(f"{rank:<6} {team_name:<35} {fmt(avg_score):>15} {roster_size:>10}")
    
    print("\n" + "=" * 80)


# ============================================================================
# MATCHUP DISPLAY FUNCTIONS
# ============================================================================

def display_matchup_results(matchup_id, team_a, team_a_stats, team_b, team_b_stats):
    """
    Display the matchup results in a formatted table.
    
    Args:
        matchup_id: Matchup ID
        team_a: ESPN Team object
        team_a_stats: Stats dict for team A
        team_b: ESPN Team object
        team_b_stats: Stats dict for team B
    """
    print()
    print("=" * 100)
    print(f"MATCHUP {matchup_id}: {team_a.team_name} vs {team_b.team_name}")
    print("=" * 100)
    
    # Display projected games played
    team_a_gp = team_a_stats.get('games_played', 0)
    team_b_gp = team_b_stats.get('games_played', 0)
    print(f"Projected Games Played: {team_a.team_name} = {team_a_gp:.0f}, {team_b.team_name} = {team_b_gp:.0f}")
    print()
    
    # Compare teams to determine winners
    category_results, team_a_wins, team_b_wins = compare_teams(
        team_a.team_name, team_a_stats,
        team_b.team_name, team_b_stats
    )
    
    # Create table header
    team_a_short = team_a.team_name[:20]  # Truncate long names
    team_b_short = team_b.team_name[:20]
    
    print(f"{'Category':<10} {team_a_short:>20} {team_b_short:>20} {'Winner':>20}")
    print("-" * 100)
    
    # Display each category
    for stat in STAT_CATEGORIES:
        a_val = team_a_stats[stat]
        b_val = team_b_stats[stat]
        winner = category_results[stat]
        
        # Format values based on stat type
        if stat == 'FT%':
            a_str = fmt(a_val)
            b_str = fmt(b_val)
        else:
            a_str = fmt(a_val, 1)
            b_str = fmt(b_val, 1)
        
        # Add checkmark for winner
        if winner == team_a.team_name:
            winner_str = f"{team_a_short} ✓"
        elif winner == team_b.team_name:
            winner_str = f"{team_b_short} ✓"
        else:
            winner_str = winner
        
        print(f"{stat:<10} {a_str:>20} {b_str:>20} {winner_str:>20}")
    
    print("-" * 100)
    print("DD sources: " + ", ".join(sorted({d['source'] for t in (team_a_stats, team_b_stats) for d in t.get('dd_sources', {}).values()})))
    if not team_a_stats.get('score_complete') or not team_b_stats.get('score_complete'):
        print("Incomplete projection: unavailable categories or provisional lineup scoring")
    print(f"{'FINAL':<10} {'':<20} {'':<20} {team_a_short} {team_a_wins}-{team_b_wins} {team_b_short:>20}")
    print("=" * 100)
    print()

