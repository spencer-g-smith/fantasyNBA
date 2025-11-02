"""
Display Fantasy NBA Team Statistics

This script calculates and displays team-level averages for each statistical
category in real-time. Supports multiple time periods via command-line arguments.
Available periods: total, last_30, last_15, last_7, projected

Usage:
    python display_team_stats.py                    # Uses projected scores (default)
    python display_team_stats.py --period total     # Uses total season scores
    python display_team_stats.py --period last_30   # Uses last 30 games
"""

import argparse
from espn_api.basketball import League

from fantasynba import (
    LEAGUE_ID,
    YEAR,
    get_league_players,
    extract_player_stats,
    add_double_doubles,
    calculate_zscores,
    build_team_dictionary,
    calculate_team_stats,
    display_team_statistics,
    display_stat_rankings,
    display_overall_rankings,
)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Display Fantasy NBA team statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python display_team_stats.py                         # Show projected scores, sorted by name
  python display_team_stats.py --period total          # Use total season scores
  python display_team_stats.py --sort overall          # Sort by overall average z-score
  python display_team_stats.py --sort PTS              # Sort by points
  python display_team_stats.py --show-rankings         # Include detailed category rankings
  python display_team_stats.py --period last_30 --sort REB  # Last 30 games, sorted by rebounds
        """
    )
    
    parser.add_argument(
        '--period',
        type=str,
        default='projected',
        choices=['total', 'last_30', 'last_15', 'last_7', 'projected'],
        help='Time period to analyze (default: projected)'
    )
    
    parser.add_argument(
        '--sort',
        type=str,
        default='name',
        help='Sort teams by: name, overall, or any stat (PTS, BLK, STL, AST, REB, 3PM, FT%%, DD)'
    )
    
    parser.add_argument(
        '--show-rankings',
        action='store_true',
        help='Show detailed category rankings'
    )
    
    return parser.parse_args()


def main():
    """Main execution function."""
    # Parse arguments
    args = parse_arguments()
    period = args.period
    sort_by = args.sort
    show_rankings = args.show_rankings
    stats_key = f'{YEAR}_{period}'
    
    print("=" * 80)
    print("FANTASY NBA TEAM STATISTICS ANALYSIS")
    print("=" * 80)
    print(f"League ID: {LEAGUE_ID}")
    print(f"Year: {YEAR}")
    print(f"Period: {period} ({stats_key})")
    print()
    
    # Connect to league
    print("Connecting to ESPN API...")
    league = League(league_id=LEAGUE_ID, year=YEAR)
    print("✓ Connected to league")
    print()
    
    # Fetch all players
    print("Fetching player data...")
    all_players, all_rostered_players, top_free_agents = get_league_players(league, YEAR)
    print(f"✓ Found {len(all_rostered_players)} rostered players")
    print(f"✓ Found {len(top_free_agents)} free agents")
    print()
    
    # Calculate z-scores in real-time
    print(f"Calculating z-scores for {period}...")
    player_stats, raw_stats = extract_player_stats(all_players, YEAR, stats_key)
    add_double_doubles(player_stats, raw_stats)
    player_zscores = calculate_zscores(player_stats, raw_stats, YEAR, stats_key)
    team_player_zscores = build_team_dictionary(league, player_zscores, top_free_agents)
    print(f"✓ Calculated z-scores for {len(player_zscores)} players")
    print()
    
    # Calculate team statistics
    print("Calculating team statistics...")
    team_stats = calculate_team_stats(team_player_zscores)
    num_teams = len([t for t in team_player_zscores.keys() if t != "Free Agents"])
    print(f"✓ Calculated statistics for {num_teams} teams")
    
    # Display main table
    display_team_statistics(team_stats, sort_by=sort_by)
    
    # Display detailed rankings if requested
    if show_rankings:
        display_stat_rankings(team_stats)
        display_overall_rankings(team_stats)
    
    print()


if __name__ == "__main__":
    main()

