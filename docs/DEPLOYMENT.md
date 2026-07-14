# Deployment

## Architecture

Single container running three services:

| Service | Port | Log Path |
|---------|------|----------|
| agent-core | 8000 | /data/logs/agent-core/ |
| mcp-core | 8001 | /data/logs/mcp-core/ |
| api-core | 8002 | /data/logs/api-core/ |

## Docker Deployment

### Build (on internet-connected machine)

```bash
cd deploy
bash build.sh
```

Produces in `deploy/output/`:
- `agentda.tar`
- `checksum.md5`

### Deploy (on air-gapped machine)

```bash
cd deploy
bash deploy.sh
```

### Manual Docker Run

```bash
docker run -d --name agentda -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -e API_CORE_URL=http://localhost:8002 \
  agentda:latest
```

## Local Development

```bash
# Terminal 1: API Core (port 8002)
cd api-core && pip install -r requirements.txt && python main.py

# Terminal 2: MCP Core (port 8001)
cd mcp-core && pip install -r requirements.txt && python main.py

# Terminal 3: Agent Core (port 8000)
cd agent-core && pip install -r requirements.txt && python main.py

# Terminal 4: MCP Client
cd mcp-client && python main.py
```

## Environment Variables

### MCP Core
| Variable | Default | Description |
|----------|---------|-------------|
| `API_CORE_URL` | `http://localhost:8002` | API Core base URL |
| `RSA_PRIVATE_KEY` | (file) | PEM-encoded RSA private key |
| `RSA_PUBLIC_KEY` | (file) | PEM-encoded RSA public key |
| `PORT` | `8001` | Service port |
| `EXPECTED_TOKEN` | `prototype-token` | Legacy auth token |

### MCP Client
| Variable | Default | Description |
|----------|---------|-------------|
| `REMOTE_MCP_URL` | `http://localhost:8001` | MCP Core URL |
| `MCP_REFRESH_TOKEN` | — | Refresh token for auth |
| `MCP_AUTH_TOKEN` | — | Legacy auth token |
