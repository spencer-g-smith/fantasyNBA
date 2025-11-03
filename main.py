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
    description="Get comprehensive player statistics including raw per-game stats, z-scores (standard deviations above/below league average), injury status, lineup slot, IR status (Injury Reserve), and overall power score for any player. Use this to evaluate individual player performance, compare players, or assess trade values. Z-scores normalize different stat categories so you can see which stats a player excels at relative to the league. Power score is the sum of all z-scores - higher is better. Supports fuzzy name matching (e.g., 'lebron' finds 'LeBron James'). Available stat_key options: 'total' (season stats, default), 'last_30', 'last_15', 'last_7' (recent form), 'projected' (preseason projections).",
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
        
        lineup_slot = getattr(player, 'lineupSlot', 'Unknown')
        
        return {
            "player_id": player.playerId,
            "player_name": player.name,
            "team": player.proTeam,
            "position": getattr(player, 'position', 'Unknown'),
            "injury_status": getattr(player, 'injuryStatus', 'Unknown'),
            "lineup_slot": lineup_slot,
            "on_ir": lineup_slot == "IR",
            "stats": stats,
            "zscores": zscores,
            "per_game_power": player_zscore_data.get("per_game_power", 0.0),
            "stat_period": stat_key,
            "full_stat_key": converted_stat_key,
            "note": "Z-scores show how many standard deviations above (positive) or below (negative) league average each stat is. A z-score of +2.0 means the player is in the top ~2% for that category, while -1.0 means below average. Power score is the sum of all z-scores - use it to compare overall player value. Higher power scores indicate more valuable fantasy players. Stats marked 'last_X' show recent form which can help identify hot/cold streaks. Injury_status shows player's current injury designation (e.g., 'OUT', 'QUESTIONABLE', 'DAY_TO_DAY', or None if healthy). Lineup_slot indicates the player's current roster position. On_ir is a boolean flag indicating if the player is on IR (Injury Reserve) - players on IR do not count against your active roster limit but cannot accumulate stats until moved off IR.",
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_player_stats: {e}")
        raise ToolError(f"Failed to retrieve player stats: {str(e)}")


@mcp.tool(
    name="get_top_free_agents",
    description="Get the top 10 available free agents ranked by power score (sum of z-scores across all categories). Use this to identify the best waiver wire pickups based on overall value or recent performance. Each player includes their game schedule for the specified matchup period and injury status, which is crucial for streaming strategies. Players with more games in a matchup period provide more counting stats. Use 'last_7' or 'last_15' to find hot pickups, or 'total' for season-long value. Automatically defaults to current matchup period. Available stat_key options: 'total' (season average, default), 'last_30', 'last_15', 'last_7' (recent form), 'projected' (preseason projections).",
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
                "injury_status": getattr(player, 'injuryStatus', None),
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
            "note": "Players are ranked by per_game_power (sum of z-scores). Higher power scores indicate better fantasy value. Check game_dates to see how many games each player has in this matchup period - more games = more opportunity for stats. Consider z-scores to see if a player fills specific category needs (e.g., high BLK z-score helps if you're weak in blocks). Use recent stat periods ('last_7', 'last_15') to identify players on hot streaks who may be emerging. Injury_status shows player's current injury designation (e.g., 'OUT', 'QUESTIONABLE', 'DAY_TO_DAY', or None if healthy) - avoid pickups with 'OUT' status.",
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_top_free_agents: {e}")
        raise ToolError(f"Failed to retrieve top free agents: {str(e)}")


@mcp.tool(
    name="get_matchup_projections",
    description="Get projected head-to-head results for all fantasy matchups in a given week. In category leagues, teams compete in 8 categories (PTS, REB, AST, STL, BLK, 3PM, FT%, DD) and the team that wins more categories wins the matchup. Results show projected wins like '6-2' meaning one team is projected to win 6 categories and lose 2. Use this for weekly strategy planning, identifying close matchups, or seeing league-wide standings projections. The stat_key determines which time period to base projections on - use 'projected' for preseason expectations, 'total' for season performance, or recent periods ('last_7', 'last_15') to account for current form, injuries, and hot/cold streaks. Automatically defaults to current matchup period. Available stat_key options: 'projected' (default), 'total', 'last_30', 'last_15', 'last_7'.",
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
            "note": "Each matchup shows a projected_result (e.g., '6-2') indicating how many of the 8 categories each team is expected to win. Category_winners shows which team wins each specific stat (PTS, REB, AST, STL, BLK, 3PM, FT%, DD). Projections are based on each team's total z-scores in that category across all active players for that matchup period. Close matchups (e.g., '5-3' or '4-4') are good opportunities for streaming players or making strategic lineup changes to flip categories. The stat_key affects projections - recent periods weight current performance while 'total' uses full season averages.",
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_matchup_projections: {e}")
        raise ToolError(f"Failed to retrieve matchup projections: {str(e)}")


@mcp.tool(
    name="get_team_projection",
    description="Get projected cumulative statistics for a specific fantasy team across all 8 categories for a matchup period. Shows the total z-scores (not raw counting stats) your team is expected to accumulate in each category based on your roster and their game schedules. Use this to analyze your team's strengths and weaknesses, identify which categories you're competitive in, or plan which stats to target via trades/pickups. Z-scores are additive - they represent how many standard deviations above/below average your entire team performs in each category. Higher z-scores mean stronger performance. Supports fuzzy team name matching. Automatically defaults to current matchup period. Available stat_key options: 'projected' (default), 'total', 'last_30', 'last_15', 'last_7'.",
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
                "FT%": team_stats.get("FT%", 0),
                "DD": team_stats.get("DD", 0),
            },
            "games_played": team_stats.get("games_played", 0),
            "note": "Projected_stats show cumulative z-scores for your team in each category (sum of all rostered players' z-scores multiplied by games played in the matchup). These are NOT raw counting stats - they're normalized scores that allow fair comparison across categories. Positive values indicate above-average team performance in that category; negative values indicate below-average. Compare your team's projections against your opponent's to see which categories you're likely to win. Games_played shows total team games in this matchup period, considering the optimized 10 player lineup. Categories with higher absolute z-scores are your team's strengths or weaknesses.",
        }
        
    except ValueError as e:
        raise ToolError(str(e))
    except Exception as e:
        logger.error(f"Error in get_team_projection: {e}")
        raise ToolError(f"Failed to retrieve team projection: {str(e)}")


@mcp.tool(
    name="get_team_roster",
    description="Get detailed roster breakdown for any fantasy team showing each player's power score, z-scores by category, and upcoming game schedule for a specific matchup period. Sorted by power score to quickly identify your best and worst performers. Use this to set optimal lineups, identify drop candidates, compare rosters across teams, or plan streaming strategies based on game schedules. The game schedule is critical - players with more games in a matchup provide more opportunities for counting stats. Z-scores by category help identify what each player contributes (e.g., specialists in BLK or 3PM). Supports fuzzy team name matching. Automatically defaults to current matchup period. Available stat_key options: 'total' (season average, default), 'last_30', 'last_15', 'last_7' (recent form), 'projected' (preseason).",
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
            "note": "Roster is sorted by per_game_power (sum of z-scores) from highest to lowest - your most valuable players are at the top. Each player's z-scores show their relative strength in each category. Game_dates lists when each player has games during this matchup period - prioritize playing players with more games. Players with 0.0 power score have no stats for the selected period (injured, not playing, etc.). Use this to optimize your starting lineup by balancing power scores with game availability. Compare category z-scores across your roster to identify if you're over/under-invested in specific stats.",
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