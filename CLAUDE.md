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
- **`api-core/`** (port 8002) — Internal REST API providing user info and financial metric queries (backed by the real FINANCE financial service)

Key security design:
- Whitelist-based metric validation (only metrics from the FINANCE dictionary are queryable)
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
  config.py            — Loads config from config/settings.json (env-overridable)
  finance_client.py    — FINANCE client: get_dictionary / get_t51_amount, dictionary cached 10 min
  requirements.txt

config/
  users.json           — User data (8 admin users, not committed to git)
  settings.json        — api-core config (FINANCE_DICTIONARY_URL, FINANCE_QUERY_URL, DICTIONARY_CACHE_TTL)

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
| `/api/finance/dictionary` | GET | Financial metrics metadata (from FINANCE `get_dictionary`, cached 10 min) |
| `/api/finance/query` | GET | Query financial data (proxies FINANCE `get_t51_amount`) |
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

用户数据保存在 `config/users.json`（含真实员工信息，未纳入版本控制），文档中不展示具体用户。
用户编号为 9 位数字，由调用方在 MCP Token 中解密获得。

## Available Financial Metrics

财务指标字典来自真实环境 FINANCE 服务 `get_dictionary` 接口（见 api-core/finance_client.py），服务缓存 10 分钟。
指标以数字编码作为 `standard_name`（如 1100000 / 1600000 / 2100000 / 2200000），中文名与同义词以接口返回为准。
查询前建议先调用 `/api/finance/dictionary` 获取最新指标列表。

Query dimensions: year, quarter (1-4), month (1-12), granularity (yearly/quarterly/monthly)

## FINANCE 财务服务配置

- 两个接口的完整地址（含 `flowActionName`）在 `config/settings.json` 中分别配置：`FINANCE_DICTIONARY_URL`（get_dictionary）/ `FINANCE_QUERY_URL`（get_t51_amount），真实地址仅在 settings.json 中配置，环境变量同名可覆盖；代码直接调用配置的地址
- `get_dictionary` 返回内容一般不变，缓存时间 `DICTIONARY_CACHE_TTL`（`config/settings.json` 中配置，默认 600 秒）
