"""
Utility functions for Fantasy NBA MCP Server.

Includes helper functions for fuzzy matching and date-based calculations.
"""

import logging
import difflib
from typing import Any, List, Optional
from datetime import datetime

from .constants import MATCHUP_SCHEDULE_2026, YEAR, LEAGUE_ID

logger = logging.getLogger(__name__)


def convert_stat_key(short_key: str) -> str:
    """
    Convert short stat key format to full ESPN format.
    
    Args:
        short_key: Short format like "last_30", "last_15", "last_7", "total", "projected"
    
    Returns:
        Full format like "2026_last_30", "2026_total", "2026_projected"
    """
    # Map common variations
    key_map = {
        "last_30": f"{YEAR}_last_30",
        "last30": f"{YEAR}_last_30",
        "last_15": f"{YEAR}_last_15",
        "last15": f"{YEAR}_last_15",
        "last_7": f"{YEAR}_last_7",
        "last7": f"{YEAR}_last_7",
        "total": f"{YEAR}_total",
        "projected": f"{YEAR}_projected",
        "projection": f"{YEAR}_projected",
    }
    
    # If already in full format, return as-is
    if short_key.startswith(f"{YEAR}_"):
        return short_key
    
    # Convert using map
    converted = key_map.get(short_key.lower())
    if not converted:
        raise ValueError(f"Invalid stat_key '{short_key}'. Valid options: {list(key_map.keys())}")
    
    return converted


def fuzzy_find_player(player_name: str, all_players: List) -> Optional[Any]:
    """
    Find a player using fuzzy name matching.
    
    Args:
        player_name: Player name to search for
        all_players: List of player objects to search
    
    Returns:
        Player object if found, None otherwise
    """
    # Create a mapping of player names to player objects
    player_dict = {player.name: player for player in all_players}
    player_names = list(player_dict.keys())
    
    # Try exact match first (case-insensitive)
    for name in player_names:
        if name.lower() == player_name.lower():
            return player_dict[name]
    
    # Use fuzzy matching
    matches = difflib.get_close_matches(player_name, player_names, n=1, cutoff=0.6)
    
    if matches:
        matched_name = matches[0]
        logger.info(f"Fuzzy matched '{player_name}' to '{matched_name}'")
        return player_dict[matched_name]
    
    return None


def get_current_matchup_id() -> int:
    """
    Determine the current matchup ID based on today's date.
    
    Returns:
        Current matchup ID (1-20)
    """
    today = datetime.now().date()
    
    # Season starts Oct 21, 2025 (scoring period 1)
    season_start = datetime(2025, 10, 21).date()
    
    if today < season_start:
        logger.info(f"Current date {today} is before season start. Defaulting to matchup 1")
        return 1
    
    # Calculate days since season start
    days_since_start = (today - season_start).days
    
    # Find which matchup we're in
    for matchup_id, scoring_periods in sorted(MATCHUP_SCHEDULE_2026.items()):
        min_period = min(scoring_periods)
        max_period = max(scoring_periods)
        
        # Each scoring period is one day
        if min_period <= days_since_start + 1 <= max_period:
            logger.info(f"Current date {today} is in matchup {matchup_id}")
            return matchup_id
    
    # If we're past all matchups, return the last one
    logger.info(f"Current date {today} is past the season. Defaulting to matchup 20")
    return 20


def fuzzy_find_team(team_name: str, teams: List) -> Optional[Any]:
    """
    Find a team using fuzzy name matching.
    
    Args:
        team_name: Team name to search for
        teams: List of team objects to search
    
    Returns:
        Team object if found, None otherwise
    """
    # Create a mapping of team names to team objects
    team_dict = {team.team_name: team for team in teams}
    team_names = list(team_dict.keys())
    
    # Try exact match first (case-insensitive)
    for name in team_names:
        if name.lower() == team_name.lower():
            return team_dict[name]
    
    # Use fuzzy matching
    matches = difflib.get_close_matches(team_name, team_names, n=1, cutoff=0.6)
    
    if matches:
        matched_name = matches[0]
        logger.info(f"Fuzzy matched team '{team_name}' to '{matched_name}'")
        return team_dict[matched_name]
    
    return None

