#!/bin/sh
cd /data/apps

# Start API Core (port 8002)
uvicorn api-core.main:app --host 0.0.0.0 --port 8002 &

# Start MCP Core (port 8001) — API_CORE_URL defaults to localhost:8002
uvicorn mcp-core.main:app --host 0.0.0.0 --port 8001 &

# Start Agent Core (port 8000)
uvicorn agent-core.main:app --host 0.0.0.0 --port 8000 &

# Wait for any child to exit
wait
