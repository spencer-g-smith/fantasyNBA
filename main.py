"""
Fantasy NBA MCP Server

A Model Context Protocol (MCP) server exposing Fantasy NBA analysis tools
using fastMCP with standard MCP patterns.
"""

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import os
from typing import Any, Dict, List, Optional
import logging
import difflib
from datetime import datetime

from espn_api.basketball import League

# Import fantasynba library functions
from fantasynba import (
    get_league_players,
    calculate_player_zscores,
    get_player_per_game_stats,
    calculate_team_matchup_stats,
    compare_teams,
    MATCHUP_SCHEDULE_2026,
    YEAR,
    LEAGUE_ID,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize fastMCP server
mcp = FastMCP("fantasy-nba-mcp", host="0.0.0.0", port=8000)


# ============================================================================
# ESPN LEAGUE INITIALIZATION
# ============================================================================

def initialize_league():
    """Initialize ESPN League with credentials from environment variables."""
    swid = os.environ.get("SWID")
    espn_s2 = os.environ.get("ESPN_S2")
    
    if not swid or not espn_s2:
        logger.warning("SWID or ESPN_S2 environment variables not set. League functionality may be limited.")
        # Try without auth for public leagues
        try:
            return League(league_id=LEAGUE_ID, year=YEAR)
        except Exception as e:
            logger.error(f"Failed to initialize league without auth: {e}")
            return None
    
    try:
        league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=espn_s2, swid=swid)
        logger.info(f"Successfully initialized ESPN League {LEAGUE_ID} for year {YEAR}")
        return league
    except Exception as e:
        logger.error(f"Failed to initialize ESPN League: {e}")
        return None


# Initialize league at module level
league = initialize_league()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

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


# ============================================================================
# MCP TOOLS - Real Fantasy NBA Functions
# ============================================================================

@mcp.tool(
    name="get_player_stats",
    description="Get player statistics with fuzzy name matching. Returns player ID, key stats, and power score. Available stat_key options: 'total' (default), 'last_30', 'last_15', 'last_7', 'projected'.",
    tags={"players", "stats"},
    meta={"version": "1.0", "category": "player-analysis"}
)
async def get_player_stats(player_name: str, stat_key: str = "total") -> Dict[str, Any]:
    """
    Get comprehensive statistics for a player.
    
    Args:
        player_name: Name of the player (supports fuzzy matching)
        stat_key: Time period for stats - 'total', 'last_30', 'last_15', 'last_7', or 'projected'
    
    Returns:
        Dictionary with player ID, name, stats, and power score
    """
    if not league:
        raise ToolError("ESPN League not initialized. Check SWID and ESPN_S2 environment variables.")
    
    try:
        # Convert stat key to full format
        converted_stat_key = convert_stat_key(stat_key)
        
        # Fetch all players
        all_players, _, _ = get_league_players(league, YEAR)
        
        # Fuzzy find the player
        player = fuzzy_find_player(player_name, all_players)
        if not player:
            raise ToolError(f"Player '{player_name}' not found. Please check the spelling and try again.")
        
        # Calculate z-scores for all players
        player_zscores = calculate_player_zscores(all_players, converted_stat_key)
        
        # Get player stats
        per_game_stats = get_player_per_game_stats(player, converted_stat_key)
        if not per_game_stats:
            raise ToolError(f"No stats available for {player.name} with stat_key '{stat_key}'")
        
        # Get z-scores for this player
        player_zscore_data = player_zscores.get(player.name, {})
        
        # Extract key stats
        stats = {
            "PTS": per_game_stats.get("PTS"),
            "REB": per_game_stats.get("REB"),
            "AST": per_game_stats.get("AST"),
            "STL": per_game_stats.get("STL"),
            "BLK": per_game_stats.get("BLK"),
            "3PM": per_game_stats.get("3PM", per_game_stats.get("3PTM")),
            "FT%": per_game_stats.get("FT%"),
        }
        
        return {
            "player_id": player.playerId,
            "player_name": player.name,
            "team": player.proTeam,
            "position": getattr(player, 'position', 'Unknown'),
            "stats": stats,
            "per_game_power": player_zscore_data.get("per_game_power", 0.0),
            "stat_period": stat_key,
            "full_stat_key": converted_stat_key,
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_player_stats: {e}")
        raise ToolError(f"Failed to retrieve player stats: {str(e)}")


@mcp.tool(
    name="get_player_power_scores",
    description="Get z-scores for all stat categories for a player. Uses fuzzy name matching. Available stat_key options: 'total' (default), 'last_30', 'last_15', 'last_7', 'projected'.",
    tags={"players", "zscores", "analytics"},
    meta={"version": "1.0", "category": "player-analysis"}
)
async def get_player_power_scores(player_name: str, stat_key: str = "total") -> Dict[str, Any]:
    """
    Get z-scores for all statistical categories for a player.
    
    Args:
        player_name: Name of the player (supports fuzzy matching)
        stat_key: Time period for stats - 'total', 'last_30', 'last_15', 'last_7', or 'projected'
    
    Returns:
        Dictionary with player name, z-scores for each category, and overall power score
    """
    if not league:
        raise ToolError("ESPN League not initialized. Check SWID and ESPN_S2 environment variables.")
    
    try:
        # Convert stat key to full format
        converted_stat_key = convert_stat_key(stat_key)
        
        # Fetch all players
        all_players, _, _ = get_league_players(league, YEAR)
        
        # Fuzzy find the player
        player = fuzzy_find_player(player_name, all_players)
        if not player:
            raise ToolError(f"Player '{player_name}' not found. Please check the spelling and try again.")
        
        # Calculate z-scores for all players
        player_zscores = calculate_player_zscores(all_players, converted_stat_key)
        
        # Get z-scores for this player
        player_zscore_data = player_zscores.get(player.name)
        if not player_zscore_data:
            raise ToolError(f"No z-score data available for {player.name} with stat_key '{stat_key}'")
        
        # Extract z-scores (exclude per_game_power as we'll return it separately)
        zscores = {
            "PTS": player_zscore_data.get("PTS", 0.0),
            "REB": player_zscore_data.get("REB", 0.0),
            "AST": player_zscore_data.get("AST", 0.0),
            "STL": player_zscore_data.get("STL", 0.0),
            "BLK": player_zscore_data.get("BLK", 0.0),
            "3PM": player_zscore_data.get("3PM", 0.0),
            "FT%": player_zscore_data.get("FT%", 0.0),
            "DD": player_zscore_data.get("DD", 0.0),
        }
        
        return {
            "player_name": player.name,
            "team": player.proTeam,
            "position": getattr(player, 'position', 'Unknown'),
            "zscores": zscores,
            "per_game_power": player_zscore_data.get("per_game_power", 0.0),
            "stat_period": stat_key,
            "full_stat_key": converted_stat_key,
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_player_power_scores: {e}")
        raise ToolError(f"Failed to retrieve player power scores: {str(e)}")


@mcp.tool(
    name="get_top_free_agents",
    description="Get top 10 free agents ranked by power score with z-scores for each category. Available stat_key options: 'total' (default), 'last_30', 'last_15', 'last_7', 'projected'.",
    tags={"free-agents", "rankings"},
    meta={"version": "1.0", "category": "roster-management"}
)
async def get_top_free_agents(stat_key: str = "total") -> Dict[str, Any]:
    """
    Get top 10 free agents ranked by power score.
    
    Args:
        stat_key: Time period for stats - 'total', 'last_30', 'last_15', 'last_7', or 'projected'
    
    Returns:
        Dictionary with stat period info and list of top free agents with power scores and z-scores
    """
    if not league:
        raise ToolError("ESPN League not initialized. Check SWID and ESPN_S2 environment variables.")
    
    try:
        # Convert stat key to full format
        converted_stat_key = convert_stat_key(stat_key)
        
        # Fetch free agents
        _, _, top_free_agents = get_league_players(league, YEAR)
        
        if not top_free_agents:
            return {
                "stat_period": stat_key,
                "full_stat_key": converted_stat_key,
                "count": 0,
                "free_agents": [],
            }
        
        # Calculate z-scores for free agents
        player_zscores = calculate_player_zscores(top_free_agents, converted_stat_key)
        
        # Create list of free agents with their power scores
        free_agent_list = []
        for player in top_free_agents:
            zscore_data = player_zscores.get(player.name)
            if not zscore_data:
                continue
            
            zscores = {
                "PTS": zscore_data.get("PTS", 0.0),
                "REB": zscore_data.get("REB", 0.0),
                "AST": zscore_data.get("AST", 0.0),
                "STL": zscore_data.get("STL", 0.0),
                "BLK": zscore_data.get("BLK", 0.0),
                "3PM": zscore_data.get("3PM", 0.0),
                "FT%": zscore_data.get("FT%", 0.0),
                "DD": zscore_data.get("DD", 0.0),
            }
            
            free_agent_list.append({
                "player_name": player.name,
                "team": player.proTeam,
                "position": getattr(player, 'position', 'Unknown'),
                "per_game_power": zscore_data.get("per_game_power", 0.0),
                "zscores": zscores,
            })
        
        # Sort by power score (descending) and take top 10
        free_agent_list.sort(key=lambda x: x["per_game_power"], reverse=True)
        top_10 = free_agent_list[:10]
        
        return {
            "stat_period": stat_key,
            "full_stat_key": converted_stat_key,
            "count": len(top_10),
            "free_agents": top_10,
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_top_free_agents: {e}")
        raise ToolError(f"Failed to retrieve top free agents: {str(e)}")


@mcp.tool(
    name="get_matchup_projections",
    description="Get projected category scores for all matchups. Defaults to current matchup based on today's date. Returns head-to-head results like '6-2'.",
    tags={"matchups", "projections"},
    meta={"version": "1.0", "category": "matchup-analysis"}
)
async def get_matchup_projections(matchup_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get projected scores for all matchups in a given matchup period.
    
    Args:
        matchup_id: Matchup period ID (1-20). Defaults to current matchup based on date.
    
    Returns:
        Dictionary with matchup projections and category winners
    """
    if not league:
        raise ToolError("ESPN League not initialized. Check SWID and ESPN_S2 environment variables.")
    
    try:
        # Use current matchup if not specified
        if matchup_id is None:
            matchup_id = get_current_matchup_id()
        
        # Validate matchup ID
        if matchup_id not in MATCHUP_SCHEDULE_2026:
            raise ValueError(f"Invalid matchup_id {matchup_id}. Must be between 1 and 20.")
        
        # Fetch all players
        all_players, _, _ = get_league_players(league, YEAR)
        
        # Calculate z-scores using projected stats
        player_zscores = calculate_player_zscores(all_players, f"{YEAR}_projected")
        
        # Calculate stats for each team
        team_stats = {}
        for team in league.teams:
            stats = calculate_team_matchup_stats(
                team, matchup_id, league, player_zscores, f"{YEAR}_projected"
            )
            team_stats[team.team_name] = stats
        
        # Get matchups for this period
        try:
            box_scores = league.box_scores(matchup_id)
        except:
            # If box_scores fails, create matchups manually
            box_scores = []
            teams = list(league.teams)
            for i in range(0, len(teams), 2):
                if i + 1 < len(teams):
                    # Create a simple object to hold the matchup
                    class SimpleMatchup:
                        def __init__(self, home, away):
                            self.home_team = home
                            self.away_team = away
                    box_scores.append(SimpleMatchup(teams[i], teams[i+1]))
        
        # Calculate projections for each matchup
        matchups = []
        for box_score in box_scores:
            team_a = box_score.home_team
            team_b = box_score.away_team
            
            team_a_stats = team_stats.get(team_a.team_name, {})
            team_b_stats = team_stats.get(team_b.team_name, {})
            
            # Compare teams
            category_results, team_a_wins, team_b_wins = compare_teams(
                team_a.team_name, team_a_stats,
                team_b.team_name, team_b_stats
            )
            
            matchups.append({
                "team_a": team_a.team_name,
                "team_b": team_b.team_name,
                "team_a_wins": team_a_wins,
                "team_b_wins": team_b_wins,
                "projected_result": f"{team_a_wins}-{team_b_wins}",
                "category_winners": category_results,
            })
        
        return {
            "matchup_id": matchup_id,
            "matchups": matchups,
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_matchup_projections: {e}")
        raise ToolError(f"Failed to retrieve matchup projections: {str(e)}")


@mcp.tool(
    name="get_team_projection",
    description="Get projected total stats for each category for a specific team in a matchup. Defaults to current matchup based on today's date.",
    tags={"teams", "projections"},
    meta={"version": "1.0", "category": "matchup-analysis"}
)
async def get_team_projection(team_name: str, matchup_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get projected statistics for a specific team in a matchup.
    
    Args:
        team_name: Name of the team (supports fuzzy matching)
        matchup_id: Matchup period ID (1-20). Defaults to current matchup based on date.
    
    Returns:
        Dictionary with team name, matchup ID, and projected stats for all categories
    """
    if not league:
        raise ToolError("ESPN League not initialized. Check SWID and ESPN_S2 environment variables.")
    
    try:
        # Use current matchup if not specified
        if matchup_id is None:
            matchup_id = get_current_matchup_id()
        
        # Validate matchup ID
        if matchup_id not in MATCHUP_SCHEDULE_2026:
            raise ValueError(f"Invalid matchup_id {matchup_id}. Must be between 1 and 20.")
        
        # Find the team using fuzzy matching
        team = fuzzy_find_team(team_name, league.teams)
        if not team:
            available_teams = [t.team_name for t in league.teams]
            raise ToolError(
                f"Team '{team_name}' not found. Available teams: {', '.join(available_teams)}"
            )
        
        # Fetch all players
        all_players, _, _ = get_league_players(league, YEAR)
        
        # Calculate z-scores using projected stats
        player_zscores = calculate_player_zscores(all_players, f"{YEAR}_projected")
        
        # Calculate team matchup stats
        team_stats = calculate_team_matchup_stats(
            team, matchup_id, league, player_zscores, f"{YEAR}_projected"
        )
        
        return {
            "team_name": team.team_name,
            "matchup_id": matchup_id,
            "projected_stats": {
                "PTS": team_stats.get("PTS", 0),
                "AST": team_stats.get("AST", 0),
                "BLK": team_stats.get("BLK", 0),
                "REB": team_stats.get("REB", 0),
                "STL": team_stats.get("STL", 0),
                "3PM": team_stats.get("3PM", 0),
                "FTM": team_stats.get("FTM", 0),
                "FTA": team_stats.get("FTA", 0),
                "FT%": team_stats.get("FT%", 0),
                "DD": team_stats.get("DD", 0),
            },
            "games_played": team_stats.get("games_played", 0),
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_team_projection: {e}")
        raise ToolError(f"Failed to retrieve team projection: {str(e)}")


# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == "__main__":
    # Get port from environment variable (for Render deployment)
    port = int(os.environ.get("PORT", 8000))
    
    logger.info("Starting Fantasy NBA MCP Server with fastMCP...")
    logger.info("MCP tools registered: get_player_stats, get_player_power_scores, get_top_free_agents, get_matchup_projections, get_team_projection")
    
    # Run the fastMCP server with SSE transport
    mcp.run(transport="stdio")