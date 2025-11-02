"""
Display Fantasy NBA Z-Score Results

This script calculates and displays player power scores and team rankings
in real-time. Supports multiple time periods via command-line arguments.
Available periods: total, last_30, last_15, last_7, projected

Usage:
    python display_results.py                    # Uses last 30 games (default)
    python display_results.py --period total     # Uses total season scores
    python display_results.py --period projected # Uses projected scores
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
    display_player_scores,
    display_team_rankings,
)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Display Fantasy NBA player z-scores and team rankings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python display_results.py                    # Use last 30 games (default)
  python display_results.py --period total     # Use total season scores
  python display_results.py --period projected # Use projected scores
  python display_results.py --period last_15   # Use last 15 games
  python display_results.py --period last_7    # Use last 7 games
        """
    )
    
    parser.add_argument(
        '--period',
        type=str,
        default='last_30',
        choices=['total', 'last_30', 'last_15', 'last_7', 'projected'],
        help='Time period to analyze (default: last_30)'
    )
    
    return parser.parse_args()


def main():
    """Main execution function."""
    # Parse arguments
    args = parse_arguments()
    period = args.period
    stats_key = f'{YEAR}_{period}'
    
    print("=" * 80)
    print("FANTASY NBA Z-SCORE ANALYSIS")
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
    
    # Display results
    display_player_scores(team_player_zscores, league.teams)
    display_team_rankings(team_player_zscores)


if __name__ == "__main__":
    main()
