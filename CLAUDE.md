# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agentda is a financial data query system built on the Model Context Protocol (MCP). It consists of three services plus an MCP client:

- **agent-core** (port 8000) — Client event/action reporting endpoint
- **mcp-core** (port 8001) — MCP remote service with RSA-encrypted token authentication
- **api-core** (port 8002) — Internal REST API providing user info and financial metric queries

## Architecture

Three independent FastAPI services:

- **`agent-core/`** (port 8000) — Receives and logs client event reports via `POST /agent/report`
- **`mcp-core/`** (port 8001) — MCP remote service that authenticates requests via RSA-encrypted tokens and proxies to api-core
- **`api-core/`** (port 8002) — Internal REST API providing user info and financial metric queries with simulated data

Key security design:
- Whitelist-based metric validation (only predefined metrics are queryable)
- Row-Level Security (RLS) — users are mapped to branches; data access is filtered by `branch_id`
- Role-based access (admin can list all users; viewer can only query own data)
- RSA-OAEP encrypted tokens (Access Token: 15min, Refresh Token: 7 days)
- Token revocation blacklist via JSON file

## File Structure

```
agent-core/
  main.py              — FastAPI app with POST /agent/report endpoint
  requirements.txt

api-core/
  main.py              — FastAPI app with user/finance endpoints
  config/
    dictionary.py      — Financial metrics dictionary, simulated data, RLS mapping
  users.json           — Mock user data (5 users, admin/viewer roles)
  requirements.txt

mcp-core/
  main.py              — MCP service: token auth, /mcp endpoint, MCP tool definitions
  config.py            — Environment-based configuration
  requirements.txt

tools/
  generate_token_py    — CLI tool for RSA key generation, token creation/decryption
  private_key.pem      — RSA private key (gitignored via .git/info/exclude)
  public_key.pem       — RSA public key
  refresh_token.txt    — Refresh token for local development
  token_records.json   — Token issuance records

deploy/
  docker-compose.yml   — Container orchestration
  build.sh             — Build Docker images and export tar
  deploy.sh            — Import tar and start services on air-gapped machine
  docker/
    api-core/Dockerfile
    mcp-core/Dockerfile
    agent-core/Dockerfile
```

## Key MCP Tools (defined in mcp-core/main.py)

| Tool | Description |
|------|-------------|
| `get_my_info` | Current user's full profile |
| `get_my_balance` | Current user's balance |
| `get_my_department` | Current user's department |
| `check_my_permission` | Current user's role (admin/viewer) |
| `list_all_users` | List all users (admin only) |
| `get_finance_dictionary` | Get financial metrics metadata |
| `query_financial_metrics` | Query financial data by metric/year/quarter/month |

All tools automatically inject the authenticated user's ID — no user_id parameter is accepted from the caller.

## API Endpoints

### Agent Core (port 8000)
| Path | Method | Description |
|------|--------|-------------|
| `/agent/report` | POST | Submit client event/action report (see ReportRequest model below) |
| `/agent/health` | GET | Health check |

**ReportRequest fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | yes | User identifier |
| client_ip | string | yes | Client IP address |
| mac_address | string | yes | Client MAC address |
| os_version | string | yes | Operating system version |
| app_name | string | yes | Application name |
| app_version | string | yes | Application version |
| screen_resolution | string | yes | Screen resolution |
| events | array[object] | yes | List of event/action items |

**ReportItem fields (inside `events` array):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| event_type | string | yes | Event type, e.g. login, call-skills, call-mcp, call-llm |
| event_params | dict | no | Event parameters (default `{}`) |
| message_content | string | yes | Event message content |
| event_time | string | yes | Event occurrence time (yyyy-MM-dd HH:mm:ss.SSS) |

**Log format (pipe delimited, no key= prefixes):**
```
<user_id>|<client_ip>|<mac_address>|<os_version>|<app_name>|<app_version>|<screen_resolution>|<event_time>|<event_type>|<event_params>|<message_content>
```

### MCP Core (port 8001)
| Path | Method | Description |
|------|--------|-------------|
| `/mcp` | POST | MCP JSON-RPC endpoint |
| `/mcp/auth/refresh` | POST | Exchange refresh token for access token |
| `/mcp/auth/revoke` | POST | Revoke a refresh token |
| `/mcp/health` | GET | Health check |

### API Core (port 8002)
| Path | Method | Description |
|------|--------|-------------|
| `/api/user/{user_id}` | GET | Get user info |
| `/api/admin/{user_id}/users` | GET | List all users (admin only) |
| `/api/finance/dictionary` | GET | Financial metrics metadata |
| `/api/finance/query` | GET | Query financial data |
| `/api/health` | GET | Health check |

## Log Paths

| Service | Log Directory | App Log | Access Log |
|---------|--------------|---------|------------|
| agent-core | /data/logs/agent-core/ | agent-core-{date}.log | agent-acc-{date}.log |
| mcp-core | /data/logs/mcp-core/ | mcp-core-{date}.log | mcp-acc-{date}.log |
| api-core | /data/logs/api-core/ | api-core-{date}.log | api-acc-{date}.log |

## Running the Services

```bash
# Agent Core (port 8000)
cd agent-core && pip install -r requirements.txt && python main.py

# MCP Core (port 8001)
cd mcp-core && pip install -r requirements.txt && python main.py

# API Core (port 8002)
cd api-core && pip install -r requirements.txt && python main.py

# MCP Client (connects to MCP Core on port 8001)
cd mcp-client && python main.py
```

## Token Management

```bash
# Generate RSA key pair
python tools/generate_token_py --generate-key

# Generate tokens for a user
python tools/generate_token_py --user-id 000000001 --refresh-expires 7

# Decrypt a token
python tools/generate_token_py --decrypt <base64-token>

# Show keys
python tools/generate_token_py --show-public-key
python tools/generate_token_py --show-private-key
```

## Test Users

| user_id | name | role | branch |
|---------|------|------|--------|
| 000000001 | 张三 | admin | BR001 |
| 000000002 | 李四 | admin | BR001 |
| 000000003 | 王五 | viewer | BR002 |
| 000000004 | 赵六 | viewer | BR001 |
| 000000005 | 钱七 | admin | BR002 |

## Available Financial Metrics

**Profitability**: NET_PROFIT (净利润), NET_INTEREST_INCOME (净利息收入)
**Scale**: TOTAL_ASSETS (资产总额), TOTAL_LIABILITIES (负债总额)
**Risk**: NPL_RATIO (不良贷款率), CAR_RATIO (资本充足率)
**Business**: LOAN_BALANCE (贷款余额), DEPOSIT_BALANCE (存款余额)

Query dimensions: year, quarter (1-4), month (1-12), granularity (yearly/quarterly/monthly)
