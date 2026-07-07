# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bankda is a financial data query system built on the Model Context Protocol (MCP). It consists of a backend API (FastAPI) and a remote MCP service that wraps the backend as MCP tools, with RSA-encrypted token authentication (Access Token + Refresh Token).

## Architecture

Two independent FastAPI services:

- **`backend_api/`** (port 8000) — Internal REST API providing user info and financial metric queries with simulated data
- **`mcp_remote/`** (port 8001) — MCP remote service that authenticates requests via RSA-encrypted tokens and proxies to the backend API

Key security design:
- Whitelist-based metric validation (only predefined metrics are queryable)
- Row-Level Security (RLS) — users are mapped to branches; data access is filtered by `branch_id`
- Role-based access (admin can list all users; viewer can only query own data)
- RSA-OAEP encrypted tokens (Access Token: 15min, Refresh Token: 7 days)
- Token revocation blacklist via JSON file

## File Structure

```
backend_api/
  main.py              — FastAPI app with user/finance endpoints
  config/
    dictionary.py      — Financial metrics dictionary, simulated data, RLS mapping
  users.json           — Mock user data (5 users, admin/viewer roles)
  requirements.txt

mcp_remote/
  main.py              — MCP service: token auth, /mcp endpoint, MCP tool definitions
  config.py            — Environment-based configuration
  requirements.txt

tools/
  generate_token_py    — CLI tool for RSA key generation, token creation/decryption
  private_key.pem      — RSA private key (gitignored via .git/info/exclude)
  public_key.pem       — RSA public key
  refresh_token.txt    — Refresh token for local development
  token_records.json   — Token issuance records
```

## Key MCP Tools (defined in mcp_remote/main.py)

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

## Running the Services

```bash
# Backend API (port 8000)
cd backend_api && pip install -r requirements.txt && python main.py

# MCP Remote (port 8001)
cd mcp_remote && pip install -r requirements.txt && python main.py
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
