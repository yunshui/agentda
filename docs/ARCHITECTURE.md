# Architecture

## System Overview

Bankda is a financial data query system built as a set of independent FastAPI microservices. The architecture follows a layered design with clear separation of concerns.

## Service Layout

```
                    ┌──────────────────────────────────────────────┐
                    │            Agent Core (port 8000)            │
                    │  POST /agent/report                          │
                    │  Client event/action reporting               │
                    └──────────────────────────────────────────────┘

                    ┌──────────────────────────────────────────────┐
                    │             MCP Core (port 8001)             │
                    │  POST /mcp            — MCP JSON-RPC        │
                    │  POST /mcp/auth/refresh — Token refresh     │
                    │  POST /mcp/auth/revoke  — Token revocation  │
                    │  GET  /mcp/health      — Health check       │
                    └──────────┬───────────────────────────────────┘
                               │ HTTP (internal)
                    ┌──────────▼───────────────────────────────────┐
                    │           API Core (port 8002)               │
                    │  GET /api/user/{id}       — User info        │
                    │  GET /api/admin/{id}/users — All users       │
                    │  GET /api/finance/dictionary — Metrics dict  │
                    │  GET /api/finance/query   — Metric data      │
                    │  GET /api/health          — Health check     │
                    └──────────────────────────────────────────────┘

                    ┌──────────────────────────────────────────────┐
                    │         Local Proxy (stdio ↔ HTTP)          │
                    │  MCP Server → localhost:8001/mcp            │
                    └──────────────────────────────────────────────┘
```

## Communication Patterns

- **Agent Core** is standalone — accepts client reports and logs them
- **MCP Core** calls **API Core** internally via HTTP for all data queries
- **Local Proxy** connects to **MCP Core** via HTTP as an MCP client
- All inter-service communication is HTTP (not message queue)

## Data Flow

```
Client App ──POST──► Agent Core (port 8000)
    │                     │ logs event
    │                     ▼
    │               /data/logs/agent-core/

Claude Code ──stdio──► Local Proxy ──HTTP──► MCP Core (port 8001)
                                                  │
                                          decrypts Token
                                                  │
                                          calls API Core (port 8002)
                                                  │
                                          queries users.json / simulated data
```

## Authentication Flow

```
1. Client sends encrypted Access Token in Authorization header
2. MCP Core decrypts with RSA private key → extracts user_id
3. All downstream API calls are authenticated via X-User-ID header
4. Refresh Token can be exchanged for new Access Token at /mcp/auth/refresh
```
