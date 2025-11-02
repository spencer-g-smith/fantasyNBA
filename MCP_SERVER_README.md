# Fantasy NBA MCP Server

An HTTP/SSE Model Context Protocol (MCP) server for Fantasy NBA analysis, built with FastAPI.

## Overview

This MCP server exposes Fantasy NBA analysis tools through the Model Context Protocol, allowing AI assistants and other MCP clients to interact with fantasy basketball data and analysis functions.

## Current Implementation

### Status
✅ **Template with Toy Functions** - Server is ready for deployment with mock data functions.

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

- **`GET /`** - API information and available tools
- **`GET /health`** - Health check for monitoring
- **`POST /sse`** - Main MCP SSE endpoint for client connections
- **`GET /messages`** - Alternative SSE endpoint
- **`GET /docs`** - Interactive API documentation (FastAPI automatic)

### Example Responses

**Health Check:**
```bash
curl https://your-server.onrender.com/health
```
```json
{
  "status": "healthy",
  "service": "fantasy-nba-mcp",
  "mcp_protocol": "http-sse",
  "tools_available": 2
}
```

**Root Endpoint:**
```bash
curl https://your-server.onrender.com/
```
```json
{
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
```

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
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
```

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

# Or with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Access the server at `http://localhost:8000`

### Test with cURL

```bash
# Health check
curl http://localhost:8000/health

# Get server info
curl http://localhost:8000/

# View API docs
open http://localhost:8000/docs
```

## MCP Client Connection

To connect an MCP client to this server:

1. **Server URL**: `https://your-server.onrender.com/sse`
2. **Protocol**: HTTP with SSE transport
3. **Tools**: Call `tools/list` to get available tools
4. **Execution**: Call `tools/call` with tool name and arguments

### Example MCP Tool Call

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_fantasy_stats",
    "arguments": {
      "player_name": "LeBron James"
    }
  },
  "id": 1
}
```

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

2. **Replace toy functions** with real implementations:
   - Use `get_league_players()` to fetch real players
   - Use `calculate_player_zscores()` for actual z-score calculations
   - Use `get_player_schedule()` for real game schedules

3. **Add new tools** from the library:
   - `get_player_schedule` - Real NBA game schedules
   - `calculate_team_stats` - Actual team statistics
   - `optimize_lineup` - Real lineup optimization
   - `project_matchup` - Actual matchup predictions

### Example Real Tool

```python
@mcp_server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    if name == "get_real_player_stats":
        league = League(league_id=LEAGUE_ID, year=YEAR)
        all_players, _, _ = get_league_players(league, YEAR)
        player_zscores = calculate_player_zscores(all_players, '2026_projected')
        
        player_name = arguments.get("player_name")
        if player_name in player_zscores:
            result = player_zscores[player_name]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
```

## Architecture

```
┌─────────────────┐
│   MCP Client    │
│  (AI Assistant) │
└────────┬────────┘
         │ HTTP/SSE
         ▼
┌─────────────────┐
│  FastAPI Server │
│   (main.py)     │
├─────────────────┤
│  MCP Protocol   │
│   Handler       │
├─────────────────┤
│  Tool Registry  │
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

- **fastapi** - Web framework
- **uvicorn** - ASGI server
- **mcp** - MCP Python SDK
- **sse-starlette** - Server-Sent Events
- **pydantic** - Data validation
- **espn-api** - ESPN Fantasy API (for future real data)

## Troubleshooting

### Server won't start
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify Python version is 3.8+
- Check logs for specific error messages

### MCP client can't connect
- Verify server is running: `curl https://your-server.onrender.com/health`
- Check that SSE endpoint is accessible: `/sse` or `/messages`
- Ensure CORS settings if connecting from browser

### Tools not working
- Check server logs for errors
- Verify tool input schema matches the call
- Test tools via `/docs` interactive interface

## Resources

- [MCP Specification](https://modelcontextprotocol.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Render Deployment Guide](https://render.com/docs/deploy-fastapi)
- [ESPN Fantasy API](https://github.com/cwendt94/espn-api)

## License

This project is for personal use in analyzing fantasy basketball leagues.

## Author

Spencer Smith

