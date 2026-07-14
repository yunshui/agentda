# Technology Stack

## Languages & Runtimes

| Component | Language | Runtime |
|-----------|----------|---------|
| All services | Python 3.12 | CPython |
| Container | - | Docker (python:3.12-slim) |

## Frameworks & Libraries

### API Core
- **FastAPI** — Web framework
- **Uvicorn** — ASGI server

### MCP Core
- **FastAPI** — Web framework for auth and MCP endpoint
- **Uvicorn** — ASGI server
- **FastMCP** (`mcp.server.fastmcp`) — MCP protocol server
- **httpx** — Async HTTP client for backend API calls
- **cryptography** — RSA-OAEP encryption/decryption

### Agent Core
- **FastAPI** — Web framework
- **Uvicorn** — ASGI server
- **Pydantic** — Request validation

### Local Proxy
- **mcp** (Python SDK) — MCP protocol client/server
- **httpx** — Async HTTP client
- **anyio** — Async runtime

### Shared
- **logging_lib.py** — Custom logging with MDC context, daily rotation, access log middleware

## Security

- **RSA-OAEP** (SHA-256) — Token encryption
- **Base64** — Token encoding
- **ContextVars** — Per-request MDC context (thread-safe)

## Infrastructure

- **Docker** — Containerization
- **Docker Compose** — Local orchestration
- **Bash** — Build/deploy scripts
