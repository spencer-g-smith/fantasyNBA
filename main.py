"""
Fantasy NBA MCP Server

A Model Context Protocol (MCP) server exposing Fantasy NBA analysis tools
using fastMCP with standard MCP patterns.
"""

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from typing import Any, Dict, List, Optional
import logging
import os

# Import ESPN League class
from espn_api.basketball import League

# Import fantasynba library functions
from fantasynba import (
    get_league_players,
    calculate_player_zscores,
    get_player_per_game_stats,
    calculate_team_matchup_stats,
    compare_teams,
    get_player_schedule,
    MATCHUP_SCHEDULE_2026,
    YEAR,
    LEAGUE_ID,
    convert_stat_key,
    fuzzy_find_player,
    get_current_matchup_id,
    fuzzy_find_team,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize fastMCP server
mcp = FastMCP("fantasy-nba-mcp", host="0.0.0.0", port=8000)


# ============================================================================
# MCP TOOLS - Real Fantasy NBA Functions
# ============================================================================

@mcp.tool(
    name="get_player_stats",
    description="Get comprehensive player statistics including raw stats, z-scores, and power score with fuzzy name matching. Available stat_key options: 'total' (default), 'last_30', 'last_15', 'last_7', 'projected' (begining of year projection.).",
    tags={"players", "stats", "zscores", "analytics"},
    meta={"version": "1.0", "category": "player-analysis"}
)
async def get_player_stats(player_name: str, stat_key: str = "total") -> Dict[str, Any]:
    """
    Get comprehensive statistics for a player including raw stats and z-scores.
    
    Args:
        player_name: Name of the player (supports fuzzy matching)
        stat_key: Time period for stats - 'total', 'last_30', 'last_15', 'last_7', or 'projected'
    
    Returns:
        Dictionary with player ID, name, raw stats, z-scores, and power score
    """
    # Initialize league with auth credentials
    swid = os.environ.get("SWID")
    espn_s2 = os.environ.get("ESPN_S2")
    
    try:
        if swid and espn_s2:
            league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=espn_s2, swid=swid)
        else:
            league = League(league_id=LEAGUE_ID, year=YEAR)
    except Exception as e:
        raise ToolError(f"Failed to initialize ESPN League: {str(e)}")
    
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
        if not player_zscore_data:
            raise ToolError(f"No z-score data available for {player.name} with stat_key '{stat_key}'")
        
        # Extract key raw stats
        stats = {
            "PTS": per_game_stats.get("PTS"),
            "REB": per_game_stats.get("REB"),
            "AST": per_game_stats.get("AST"),
            "STL": per_game_stats.get("STL"),
            "BLK": per_game_stats.get("BLK"),
            "3PM": per_game_stats.get("3PM", per_game_stats.get("3PTM")),
            "FT%": per_game_stats.get("FT%"),
        }
        
        # Extract z-scores for all categories
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
            "player_id": player.playerId,
            "player_name": player.name,
            "team": player.proTeam,
            "position": getattr(player, 'position', 'Unknown'),
            "stats": stats,
            "zscores": zscores,
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
    name="get_top_free_agents",
    description="Get top 10 free agents ranked by power score with z-scores for each category and their game dates for the specified matchup. Available stat_key options: 'total' (default), 'last_30', 'last_15', 'last_7', 'projected'. Defaults to current matchup based on today's date.",
    tags={"free-agents", "rankings"},
    meta={"version": "1.0", "category": "roster-management"}
)
async def get_top_free_agents(stat_key: str = "total", matchup_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get top 10 free agents ranked by power score with game dates for the specified matchup.
    
    Args:
        stat_key: Time period for stats - 'total', 'last_30', 'last_15', 'last_7', or 'projected'
        matchup_id: Matchup period ID (1-20). Defaults to current matchup based on date.
    
    Returns:
        Dictionary with stat period info, matchup info, and list of top free agents with power scores, z-scores, and game dates
    """
    # Initialize league with auth credentials
    swid = os.environ.get("SWID")
    espn_s2 = os.environ.get("ESPN_S2")
    
    try:
        if swid and espn_s2:
            league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=espn_s2, swid=swid)
        else:
            league = League(league_id=LEAGUE_ID, year=YEAR)
    except Exception as e:
        raise ToolError(f"Failed to initialize ESPN League: {str(e)}")
    
    try:
        # Use current matchup if not specified
        if matchup_id is None:
            matchup_id = get_current_matchup_id()
        
        # Validate matchup ID
        if matchup_id not in MATCHUP_SCHEDULE_2026:
            raise ValueError(f"Invalid matchup_id {matchup_id}. Must be between 1 and 20.")
        
        # Convert stat key to full format
        converted_stat_key = convert_stat_key(stat_key)
        
        # Fetch free agents
        _, _, top_free_agents = get_league_players(league, YEAR)
        
        if not top_free_agents:
            return {
                "stat_period": stat_key,
                "full_stat_key": converted_stat_key,
                "matchup_id": matchup_id,
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
            
            # Get player's game schedule for the matchup
            schedule = get_player_schedule(player, matchup_id, league)
            game_dates = [game['date'].isoformat() for game in schedule]
            
            free_agent_list.append({
                "player_name": player.name,
                "team": player.proTeam,
                "position": getattr(player, 'position', 'Unknown'),
                "per_game_power": zscore_data.get("per_game_power", 0.0),
                "zscores": zscores,
                "game_dates": {matchup_id: game_dates},
            })
        
        # Sort by power score (descending) and take top 10
        free_agent_list.sort(key=lambda x: x["per_game_power"], reverse=True)
        top_10 = free_agent_list[:10]
        
        return {
            "stat_period": stat_key,
            "full_stat_key": converted_stat_key,
            "matchup_id": matchup_id,
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
    description="Get projected category scores for all matchups. Available stat_key options: 'projected' (default), 'total', 'last_30', 'last_15', 'last_7'. Defaults to current matchup based on today's date. Returns head-to-head results like '6-2'.",
    tags={"matchups", "projections"},
    meta={"version": "1.0", "category": "matchup-analysis"}
)
async def get_matchup_projections(matchup_id: Optional[int] = None, stat_key: str = "projected") -> Dict[str, Any]:
    """
    Get projected scores for all matchups in a given matchup period.
    
    Args:
        matchup_id: Matchup period ID (1-20). Defaults to current matchup based on date.
        stat_key: Time period for stats - 'projected', 'total', 'last_30', 'last_15', or 'last_7'
    
    Returns:
        Dictionary with matchup projections and category winners
    """
    # Initialize league with auth credentials
    swid = os.environ.get("SWID")
    espn_s2 = os.environ.get("ESPN_S2")
    
    try:
        if swid and espn_s2:
            league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=espn_s2, swid=swid)
        else:
            league = League(league_id=LEAGUE_ID, year=YEAR)
    except Exception as e:
        raise ToolError(f"Failed to initialize ESPN League: {str(e)}")
    
    try:
        # Use current matchup if not specified
        if matchup_id is None:
            matchup_id = get_current_matchup_id()
        
        # Validate matchup ID
        if matchup_id not in MATCHUP_SCHEDULE_2026:
            raise ValueError(f"Invalid matchup_id {matchup_id}. Must be between 1 and 20.")
        
        # Convert stat key to full format
        converted_stat_key = convert_stat_key(stat_key)
        
        # Fetch all players
        all_players, _, _ = get_league_players(league, YEAR)
        
        # Calculate z-scores using specified stats
        player_zscores = calculate_player_zscores(all_players, converted_stat_key)
        
        # Calculate stats for each team
        team_stats = {}
        for team in league.teams:
            stats = calculate_team_matchup_stats(
                team, matchup_id, league, player_zscores, converted_stat_key
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
            "stat_period": stat_key,
            "full_stat_key": converted_stat_key,
            "matchups": matchups,
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_matchup_projections: {e}")
        raise ToolError(f"Failed to retrieve matchup projections: {str(e)}")


@mcp.tool(
    name="get_team_projection",
    description="Get projected total stats for each category for a specific team in a matchup. Available stat_key options: 'projected' (default), 'total', 'last_30', 'last_15', 'last_7'. Defaults to current matchup based on today's date.",
    tags={"teams", "projections"},
    meta={"version": "1.0", "category": "matchup-analysis"}
)
async def get_team_projection(team_name: str, matchup_id: Optional[int] = None, stat_key: str = "projected") -> Dict[str, Any]:
    """
    Get projected statistics for a specific team in a matchup.
    
    Args:
        team_name: Name of the team (supports fuzzy matching)
        matchup_id: Matchup period ID (1-20). Defaults to current matchup based on date.
        stat_key: Time period for stats - 'projected', 'total', 'last_30', 'last_15', or 'last_7'
    
    Returns:
        Dictionary with team name, matchup ID, stat period, and projected stats for all categories
    """
    # Initialize league with auth credentials
    swid = os.environ.get("SWID")
    espn_s2 = os.environ.get("ESPN_S2")
    
    try:
        if swid and espn_s2:
            league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=espn_s2, swid=swid)
        else:
            league = League(league_id=LEAGUE_ID, year=YEAR)
    except Exception as e:
        raise ToolError(f"Failed to initialize ESPN League: {str(e)}")
    
    try:
        # Use current matchup if not specified
        if matchup_id is None:
            matchup_id = get_current_matchup_id()
        
        # Validate matchup ID
        if matchup_id not in MATCHUP_SCHEDULE_2026:
            raise ValueError(f"Invalid matchup_id {matchup_id}. Must be between 1 and 20.")
        
        # Convert stat key to full format
        converted_stat_key = convert_stat_key(stat_key)
        
        # Find the team using fuzzy matching
        team = fuzzy_find_team(team_name, league.teams)
        if not team:
            available_teams = [t.team_name for t in league.teams]
            raise ToolError(
                f"Team '{team_name}' not found. Available teams: {', '.join(available_teams)}"
            )
        
        # Fetch all players
        all_players, _, _ = get_league_players(league, YEAR)
        
        # Calculate z-scores using specified stats
        player_zscores = calculate_player_zscores(all_players, converted_stat_key)
        
        # Calculate team matchup stats
        team_stats = calculate_team_matchup_stats(
            team, matchup_id, league, player_zscores, converted_stat_key
        )
        
        return {
            "team_name": team.team_name,
            "matchup_id": matchup_id,
            "stat_period": stat_key,
            "full_stat_key": converted_stat_key,
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


@mcp.tool(
    name="get_team_roster",
    description="Get roster for a fantasy team with each player's powerscore and game schedule for the specified stat period and matchup. Available stat_key options: 'total' (default), 'last_30', 'last_15', 'last_7', 'projected'. Defaults to current matchup based on today's date.",
    tags={"teams", "roster", "stats", "schedule"},
    meta={"version": "1.0", "category": "team-analysis"}
)
async def get_team_roster(team: str, stat_key: str = "total", matchup_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get roster for a fantasy team with each player's powerscore and game schedule for the specified stat period.
    
    Args:
        team: Name of the team (supports fuzzy matching)
        stat_key: Time period for stats - 'total', 'last_30', 'last_15', 'last_7', or 'projected'
        matchup_id: Matchup period ID (1-20) for game schedules. Defaults to current matchup based on date.
    
    Returns:
        Dictionary with team name, stat period, matchup ID, roster count, and list of players with powerscores and game dates
    """
    # Initialize league with auth credentials
    swid = os.environ.get("SWID")
    espn_s2 = os.environ.get("ESPN_S2")
    
    try:
        if swid and espn_s2:
            league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=espn_s2, swid=swid)
        else:
            league = League(league_id=LEAGUE_ID, year=YEAR)
    except Exception as e:
        raise ToolError(f"Failed to initialize ESPN League: {str(e)}")
    
    try:
        # Use current matchup if not specified
        if matchup_id is None:
            matchup_id = get_current_matchup_id()
        
        # Validate matchup ID
        if matchup_id not in MATCHUP_SCHEDULE_2026:
            raise ValueError(f"Invalid matchup_id {matchup_id}. Must be between 1 and 20.")
        
        # Find the team using fuzzy matching
        fantasy_team = fuzzy_find_team(team, league.teams)
        if not fantasy_team:
            available_teams = [t.team_name for t in league.teams]
            raise ToolError(
                f"Team '{team}' not found. Available teams: {', '.join(available_teams)}"
            )
        
        # Convert stat key if needed (e.g., "total" -> "total_2026")
        converted_stat_key = convert_stat_key(stat_key)
        
        # Fetch all players to calculate z-scores
        all_players, _, _ = get_league_players(league, YEAR)
        
        # Calculate z-scores for all players
        player_zscores = calculate_player_zscores(all_players, converted_stat_key)
        
        # Get roster for this team
        roster = []
        for player in fantasy_team.roster:
            # Get player's game schedule for the matchup
            schedule = get_player_schedule(player, matchup_id, league)
            game_dates = [game['date'].isoformat() for game in schedule]
            
            # Get z-score data for this player
            zscore_data = player_zscores.get(player.name)
            if not zscore_data:
                # Player has no stats for this period, include with 0 powerscore
                roster.append({
                    "player_name": player.name,
                    "team": player.proTeam,
                    "position": getattr(player, 'position', 'Unknown'),
                    "per_game_power": 0.0,
                    "zscores": {
                        "PTS": 0.0,
                        "REB": 0.0,
                        "AST": 0.0,
                        "STL": 0.0,
                        "BLK": 0.0,
                        "3PM": 0.0,
                        "FT%": 0.0,
                        "DD": 0.0,
                    },
                    "game_dates": {matchup_id: game_dates},
                })
                continue
            
            # Extract z-scores
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
            
            roster.append({
                "player_name": player.name,
                "team": player.proTeam,
                "position": getattr(player, 'position', 'Unknown'),
                "per_game_power": zscore_data.get("per_game_power", 0.0),
                "zscores": zscores,
                "game_dates": {matchup_id: game_dates},
            })
        
        # Sort by powerscore (descending)
        roster.sort(key=lambda x: x["per_game_power"], reverse=True)
        
        return {
            "team_name": fantasy_team.team_name,
            "stat_period": stat_key,
            "full_stat_key": converted_stat_key,
            "matchup_id": matchup_id,
            "roster_count": len(roster),
            "roster": roster,
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_team_roster: {e}")
        raise ToolError(f"Failed to retrieve team roster: {str(e)}")


# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting Fantasy NBA MCP Server with fastMCP...")
    logger.info("MCP tools registered: get_player_stats, get_top_free_agents, get_matchup_projections, get_team_projection, get_team_roster")
    
    # Run the fastMCP server with SSE transport
    mcp.run(transport="sse")