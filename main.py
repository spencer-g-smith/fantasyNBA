"""
Fantasy NBA MCP Server

A Model Context Protocol (MCP) server exposing Fantasy NBA analysis tools
via HTTP/SSE transport using FastAPI.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.sse import SseServerTransport
import json
import asyncio
from typing import Any, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Fantasy NBA MCP Server",
    description="Model Context Protocol server for Fantasy NBA analysis",
    version="1.0.0"
)

# Initialize MCP server
mcp_server = Server("fantasy-nba-mcp")


# ============================================================================
# MCP TOOLS - Toy Functions
# ============================================================================

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available MCP tools."""
    return [
        Tool(
            name="get_fantasy_stats",
            description="Get mock fantasy basketball statistics for a player. Returns points, rebounds, and assists averages.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player_name": {
                        "type": "string",
                        "description": "The name of the NBA player"
                    }
                },
                "required": ["player_name"]
            }
        ),
        Tool(
            name="compare_players",
            description="Compare mock statistics between two players. Returns a comparison of their fantasy stats.",
            inputSchema={
                "type": "object",
                "properties": {
                    "player1": {
                        "type": "string",
                        "description": "Name of the first player"
                    },
                    "player2": {
                        "type": "string",
                        "description": "Name of the second player"
                    }
                },
                "required": ["player1", "player2"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """Execute an MCP tool by name."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    try:
        if name == "get_fantasy_stats":
            result = await get_fantasy_stats(arguments.get("player_name", "Unknown"))
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "compare_players":
            result = await compare_players(
                arguments.get("player1", "Player 1"),
                arguments.get("player2", "Player 2")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"})
            )]
    
    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}")
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e)})
        )]


# ============================================================================
# TOY FUNCTIONS - Mock Data
# ============================================================================

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
            "points": round(15 + (hash_val % 20), 1),
            "rebounds": round(5 + (hash_val % 10), 1),
            "assists": round(3 + (hash_val % 8), 1),
            "steals": round(0.5 + (hash_val % 3), 1),
            "blocks": round(0.3 + (hash_val % 2), 1),
            "three_pointers": round(1 + (hash_val % 4), 1),
            "free_throw_pct": round(0.70 + (hash_val % 30) / 100, 3)
        },
        "per_game_power": round(10 + (hash_val % 30), 2),
        "note": "This is mock data. Real implementation will use ESPN API."
    }


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
# FASTAPI ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Fantasy NBA MCP Server",
        "version": "1.0.0",
        "description": "Model Context Protocol server for Fantasy NBA analysis",
        "endpoints": {
            "health": "/health",
            "mcp_sse": "/sse",
            "docs": "/docs"
        },
        "tools": [
            "get_fantasy_stats - Get fantasy stats for a player",
            "compare_players - Compare two players' stats"
        ],
        "status": "active"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring."""
    return {
        "status": "healthy",
        "service": "fantasy-nba-mcp",
        "mcp_protocol": "http-sse",
        "tools_available": 2
    }


@app.get("/sse")
async def handle_sse(request: Request):
    """
    SSE endpoint for MCP protocol communication.
    
    This endpoint handles the Server-Sent Events transport for MCP.
    Clients connect to this endpoint to interact with the MCP server.
    
    Returns text/event-stream with proper SSE formatting.
    """
    async def event_stream():
        """Generate SSE events for MCP communication."""
        logger.info("SSE connection established")
        
        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "type": "connected",
                    "server": "fantasy-nba-mcp",
                    "version": "1.0.0",
                    "timestamp": asyncio.get_event_loop().time()
                })
            }
            
            # Send available tools
            tools = await list_tools()
            yield {
                "event": "tools",
                "data": json.dumps({
                    "type": "tools",
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description
                        } for tool in tools
                    ]
                })
            }
            
            # Keep connection alive with periodic pings
            counter = 0
            while True:
                await asyncio.sleep(5)
                counter += 1
                yield {
                    "event": "ping",
                    "data": json.dumps({
                        "type": "ping",
                        "count": counter,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                }
                
        except asyncio.CancelledError:
            logger.info("SSE connection closed by client")
            raise
        except Exception as e:
            logger.error(f"SSE stream error: {str(e)}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "error": str(e)
                })
            }
    
    return EventSourceResponse(event_stream())


@app.get("/messages")
async def handle_messages():
    """
    Alternative endpoint for SSE messages.
    Some MCP clients may use this endpoint.
    """
    async def event_stream():
        """Generate SSE events."""
        try:
            async with SseServerTransport("/messages") as transport:
                await mcp_server.connect(transport)
                
                # Keep connection alive
                while True:
                    await asyncio.sleep(1)
                    yield {
                        "event": "ping",
                        "data": json.dumps({"type": "ping"})
                    }
                    
        except Exception as e:
            logger.error(f"Messages stream error: {str(e)}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
    
    return EventSourceResponse(event_stream())


# ============================================================================
# APPLICATION STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize the MCP server on application startup."""
    logger.info("Starting Fantasy NBA MCP Server...")
    logger.info("MCP tools registered: get_fantasy_stats, compare_players")
    logger.info("Server ready to accept connections")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down Fantasy NBA MCP Server...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

