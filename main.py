"""
Fantasy NBA MCP Server

A Model Context Protocol (MCP) server exposing Fantasy NBA analysis tools
using fastMCP with standard MCP patterns.
"""

from fastmcp import FastMCP
import os
from typing import Any, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize fastMCP server
mcp = FastMCP("fantasy-nba-mcp")


# ============================================================================
# MCP TOOLS - Mock Data Functions
# ============================================================================

@mcp.tool()
async def get_fantasy_stats(player_name: str) -> Dict[str, Any]:
    """
    Mock function that returns fantasy stats for a player.
    
    In production, this would fetch real data from ESPN API and calculate
    z-scores using the fantasynba library.
    """
    # Mock data based on player name hash for consistent "stats"
    hash_val = sum(ord(c) for c in player_name)
    
    return {
        "player": player_name,
        "stats": {
            # Hard-coded sample stats for mock response
            "points": 26.4,
            "rebounds": 8.1,
            "assists": 7.3,
            "steals": 1.5,
            "blocks": 0.8,
            "three_pointers": 2.4,
            "free_throw_pct": 0.812
        },
        "per_game_power": 27.8,
        "note": "This is mock data. Real implementation will use ESPN API."
    }


@mcp.tool()
async def compare_players(player1: str, player2: str) -> Dict[str, Any]:
    """
    Mock function that compares two players' fantasy stats.
    
    In production, this would use calculate_player_zscores and compare
    real statistics.
    """
    stats1 = await get_fantasy_stats(player1)
    stats2 = await get_fantasy_stats(player2)
    
    comparison = {
        "player1": player1,
        "player2": player2,
        "comparison": {},
        "winner": None
    }
    
    # Compare each stat
    for stat in ["points", "rebounds", "assists", "steals", "blocks"]:
        val1 = stats1["stats"][stat]
        val2 = stats2["stats"][stat]
        comparison["comparison"][stat] = {
            player1: val1,
            player2: val2,
            "difference": round(val1 - val2, 1),
            "winner": player1 if val1 > val2 else player2 if val2 > val1 else "tie"
        }
    
    # Overall winner based on per_game_power
    if stats1["per_game_power"] > stats2["per_game_power"]:
        comparison["winner"] = player1
    elif stats2["per_game_power"] > stats1["per_game_power"]:
        comparison["winner"] = player2
    else:
        comparison["winner"] = "tie"
    
    comparison["note"] = "This is mock data. Real implementation will use z-scores."
    
    return comparison


# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == "__main__":
    # Get port from environment variable (for Render deployment)
    port = int(os.environ.get("PORT", 8000))
    
    logger.info("Starting Fantasy NBA MCP Server with fastMCP...")
    logger.info("MCP tools registered: get_fantasy_stats, compare_players")
    
    # Run the fastMCP server with SSE transport
    mcp.run(transport="stdio")

