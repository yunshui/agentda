# Deployment

## Architecture

Three Docker containers:

| Service | Port | Image | Log Path |
|---------|------|-------|----------|
| agent-core | 8000 | bankda-agent-core:latest | /data/logs/agent-core/ |
| mcp-core | 8001 | bankda-mcp-core:latest | /data/logs/mcp-core/ |
| api-core | 8002 | bankda-api-core:latest | /data/logs/api-core/ |

## Docker Deployment

### Build (on internet-connected machine)

```bash
cd deploy
bash build.sh
```

Produces in `deploy/output/`:
- `bankda-api-core.tar`
- `bankda-mcp-core.tar`
- `bankda-agent-core.tar`
- `checksum.md5`

### Deploy (on air-gapped machine)

```bash
cd deploy
bash deploy.sh
```

### Manual Docker Run

```bash
# API Core
docker run -d --name api-core -p 8002:8002 bankda-api-core:latest

# MCP Core
docker run -d --name mcp-core -p 8001:8001 \
  -e BACKEND_API_URL=http://api-core:8002 \
  bankda-mcp-core:latest

# Agent Core
docker run -d --name agent-core -p 8000:8000 bankda-agent-core:latest
```

## Local Development

```bash
# Terminal 1: API Core (port 8002)
cd api-core && pip install -r requirements.txt && python main.py

# Terminal 2: MCP Core (port 8001)
cd mcp-core && pip install -r requirements.txt && python main.py

# Terminal 3: Agent Core (port 8000)
cd agent-core && pip install -r requirements.txt && python main.py

# Terminal 4: Local Proxy
cd local_proxy && python main.py
```

## Environment Variables

### MCP Core
| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_API_URL` | `http://localhost:8002` | API Core base URL |
| `RSA_PRIVATE_KEY` | (file) | PEM-encoded RSA private key |
| `RSA_PUBLIC_KEY` | (file) | PEM-encoded RSA public key |
| `PORT` | `8001` | Service port |
| `EXPECTED_TOKEN` | `prototype-token` | Legacy auth token |

### Local Proxy
| Variable | Default | Description |
|----------|---------|-------------|
| `REMOTE_MCP_URL` | `http://localhost:8001` | MCP Core URL |
| `MCP_REFRESH_TOKEN` | — | Refresh token for auth |
| `MCP_AUTH_TOKEN` | — | Legacy auth token |
