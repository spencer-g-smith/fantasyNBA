"""
Project Matchup Scores for Fantasy NBA Teams

This script calculates projected matchup scores by optimizing daily lineups
for each scoring period within a matchup, then comparing head-to-head results.
All calculations are performed in real-time.

Usage:
    python project_matchup_scores.py 3              # Project matchup 3
    python project_matchup_scores.py 5 --period last_7   # Use last 7 games data
"""

import argparse
from espn_api.basketball import League

from fantasynba import (
    LEAGUE_ID,
    YEAR,
    get_league_players,
    calculate_player_zscores,
    calculate_team_matchup_stats,
    display_matchup_results,
)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Project matchup scores for fantasy basketball teams',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python project_matchup_scores.py 3              # Project matchup 3
  python project_matchup_scores.py 5 --period last_7   # Use last 7 games data
        """
    )
    
    parser.add_argument(
        'matchup_id',
        type=int,
        help='Matchup ID to project (1-20)'
    )
    
    parser.add_argument(
        '--period',
        type=str,
        default='projected',
        choices=['total', 'last_30', 'last_15', 'last_7', 'projected'],
        help='Time period to use for per-game averages (default: projected)'
    )
    
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_arguments()
    matchup_id = args.matchup_id
    period = args.period
    stats_key = f'{YEAR}_{period}'
    
    print("=" * 80)
    print("PROJECTING MATCHUP SCORES")
    print("=" * 80)
    print(f"League ID: {LEAGUE_ID}")
    print(f"Year: {YEAR}")
    print(f"Matchup ID: {matchup_id}")
    print(f"Stats Period: {period} ({stats_key})")
    print()
    
    # Initialize league
    print("Connecting to ESPN API...")
    league = League(league_id=LEAGUE_ID, year=YEAR)
    print("✓ Connected to league")
    print()
    
    # Get matchup from scoreboard
    print(f"Fetching matchup {matchup_id}...")
    matchups = league.scoreboard(matchup_id)
    
    if not matchups or len(matchups) == 0:
        print(f"Error: No matchups found for ID {matchup_id}")
        return
    
    print(f"✓ Found {len(matchups)} matchup(s) for period {matchup_id}")
    print()
    
    # Get all rostered players for z-score calculation
    print("Calculating z-scores for all players...")
    all_players, _, _ = get_league_players(league, YEAR)
    player_zscores = calculate_player_zscores(all_players, stats_key)
    print(f"✓ Calculated z-scores for {len(player_zscores)} players")
    print()
    
    # Process each matchup in the scoring period
    for idx, box_score in enumerate(matchups, 1):
        team_a = box_score.home_team
        team_b = box_score.away_team
        
        print(f"Processing matchup {idx}/{len(matchups)}: {team_a.team_name} vs {team_b.team_name}...")
        
        # Calculate stats for both teams
        team_a_stats = calculate_team_matchup_stats(team_a, matchup_id, league, player_zscores, stats_key)
        team_b_stats = calculate_team_matchup_stats(team_b, matchup_id, league, player_zscores, stats_key)
        
        print(f"✓ Completed")
        
        # Display results
        display_matchup_results(matchup_id, team_a, team_a_stats, team_b, team_b_stats)


if __name__ == "__main__":
    main()
