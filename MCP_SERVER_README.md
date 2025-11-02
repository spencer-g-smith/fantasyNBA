# Fantasy NBA MCP Server

A Model Context Protocol (MCP) server for Fantasy NBA analysis, built with fastMCP.

## Overview

This MCP server exposes Fantasy NBA analysis tools through the Model Context Protocol, allowing AI assistants and other MCP clients to interact with fantasy basketball data and analysis functions using standard fastMCP patterns.

## Current Implementation

### Status
✅ **fastMCP Implementation with Mock Functions** - Server uses standard MCP patterns and is ready for deployment with mock data functions.

### Available Tools

1. **get_fantasy_stats**
   - Get mock fantasy basketball statistics for a player
   - Input: `player_name` (string)
   - Returns: Points, rebounds, assists, steals, blocks, 3PM, FT%, and per-game power score
   - Note: Currently returns mock data based on player name hash

2. **compare_players**
   - Compare mock statistics between two players
   - Input: `player1` (string), `player2` (string)
   - Returns: Side-by-side comparison with winner determination
   - Note: Currently uses mock data

## Endpoints

### Primary Endpoints

fastMCP automatically generates the necessary MCP endpoints:

- **`/mcp/v1`** - Main MCP endpoint for protocol communication
- **`/health`** - Health check endpoint (built-in with fastMCP)
- Additional endpoints are managed automatically by fastMCP

### Example Responses

**Health Check:**
```bash
curl https://your-server.onrender.com/health
```

fastMCP provides automatic health checking and status endpoints.

## Deployment

### Render Configuration

The server is configured for deployment on Render with the following setup:

```yaml
services:
  - type: web
    name: fantasynba
    runtime: python
    plan: free
    autoDeploy: true
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
```

The server automatically reads the `PORT` environment variable from Render and starts with HTTP transport.

### Deploy Steps

1. **Push to Git**: Commit and push changes to your repository
2. **Connect to Render**: Link your repository in Render dashboard
3. **Automatic Deployment**: Render will build and deploy automatically
4. **Access**: Your server will be available at `https://fantasynba.onrender.com`

## Local Development

### Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```

The server will start on `http://localhost:8000` by default.

### Test with cURL

```bash
# Health check
curl http://localhost:8000/health

# Test MCP endpoint
curl http://localhost:8000/mcp/v1
```

## MCP Protocol Flow

This server implements the MCP protocol using fastMCP's built-in **HTTP transport**.

### Connection Flow

fastMCP automatically handles:
- Protocol negotiation and initialization
- Tool discovery and registration
- Request/response handling
- Error handling and logging

The standard MCP protocol flow is managed entirely by fastMCP, requiring no manual implementation.

## MCP Client Connection

To connect an MCP client (like Claude Desktop) to this server:

1. **Server URL**: `https://your-server.onrender.com/mcp/v1`
2. **Protocol**: HTTP (fastMCP transport)
3. **Tools**: Automatically discovered via MCP protocol
4. **Execution**: Call tools via standard MCP methods

### Tool Definition

Tools are defined using the `@mcp.tool()` decorator:

```python
@mcp.tool()
async def get_fantasy_stats(player_name: str) -> Dict[str, Any]:
    """Get mock fantasy basketball statistics for a player."""
    # Implementation
    return {...}
```

fastMCP automatically:
- Generates the tool schema from type hints
- Handles tool registration and discovery
- Manages request/response serialization

## Next Steps

### Connecting to Real Data

To connect to your ESPN Fantasy Basketball league:

1. **Update `main.py`** to import from `fantasynba` package:
   ```python
   from fantasynba import (
       get_league_players,
       calculate_player_zscores,
       calculate_team_matchup_stats,
       LEAGUE_ID, YEAR
   )
   from espn_api.basketball import League
   ```

2. **Replace mock tool functions** with real implementations:
   - Use `get_league_players()` to fetch real players
   - Use `calculate_player_zscores()` for actual z-score calculations
   - Use `get_player_schedule()` for real game schedules

3. **Add new tools** using `@mcp.tool()` decorator:
   - `get_player_schedule` - Real NBA game schedules
   - `calculate_team_stats` - Actual team statistics
   - `optimize_lineup` - Real lineup optimization
   - `project_matchup` - Actual matchup predictions

### Example Real Tool with fastMCP

```python
@mcp.tool()
async def get_real_player_stats(player_name: str) -> dict:
    """Get real player statistics from ESPN Fantasy Basketball."""
    league = League(league_id=LEAGUE_ID, year=YEAR)
    all_players, _, _ = get_league_players(league, YEAR)
    player_zscores = calculate_player_zscores(all_players, '2026_projected')
    
    if player_name in player_zscores:
        return player_zscores[player_name]
    else:
        return {"error": f"Player {player_name} not found"}
```

## Architecture

```
┌─────────────────┐
│   MCP Client    │
│  (AI Assistant) │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  fastMCP Server │
│   (main.py)     │
├─────────────────┤
│  Auto Protocol  │
│    Handling     │
├─────────────────┤
│  Tool Registry  │
│  @mcp.tool()    │
│  - get_fantasy_ │
│    stats        │
│  - compare_     │
│    players      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  fantasynba lib │
│  (Future)       │
│  - players.py   │
│  - stats.py     │
│  - matchups.py  │
└─────────────────┘
```

## Dependencies

- **fastmcp** - FastMCP framework (includes MCP protocol handling)
- **espn-api** - ESPN Fantasy API (for future real data)
- **numpy** / **scipy** - Statistical calculations (via fantasynba library)

## Troubleshooting

### Server won't start
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify Python version is 3.11+
- Check logs for specific error messages
- Ensure `fastmcp` is installed: `pip install fastmcp`

### MCP client can't connect
- Verify server is running: `curl https://your-server.onrender.com/health`
- Check that MCP endpoint is accessible: `/mcp/v1`
- Verify the correct server URL is configured in your MCP client

### Tools not working
- Check server logs for errors
- Verify tool function signatures match expected types
- Ensure tool docstrings are properly formatted
- Check that return types are JSON-serializable

### Implementation Notes

This server now uses **fastMCP**, which provides:
- Automatic protocol handling (no manual JSON-RPC implementation needed)
- Built-in tool registration via decorators
- Standard MCP patterns and best practices
- Simplified deployment and maintenance

## Resources

- [MCP Specification](https://modelcontextprotocol.io/)
- [fastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Render Deployment Guide](https://render.com/docs)
- [ESPN Fantasy API](https://github.com/cwendt94/espn-api)

## License

This project is for personal use in analyzing fantasy basketball leagues.

## Author

Spencer Smith

