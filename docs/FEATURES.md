# Features

## 1. User Information

| Endpoint | Description | Auth Required |
|----------|-------------|---------------|
| `GET /api/user/{user_id}` | Get user profile (name, dept, role, balance) | Via MCP Core |
| `GET /api/admin/{user_id}/users` | List all users (admin only) | Via MCP Core |

### MCP Tools
- `get_my_info` — Full profile of authenticated user
- `get_my_balance` — Account balance only
- `get_my_department` — Department info only
- `check_my_permission` — Role/privilege check
- `list_all_users` — All users (admin-only)

## 2. Financial Metrics

| Endpoint | Description |
|----------|-------------|
| `GET /api/finance/dictionary` | Available metrics metadata |
| `GET /api/finance/query` | Query metric data by dimensions |

### MCP Tools
- `get_finance_dictionary` — Available metrics
- `query_financial_metrics` — Query metrics by year/quarter/month

### Available Metrics

| Category | Metric | Unit |
|----------|--------|------|
| Profitability | NET_PROFIT (净利润) | 万元 |
| Profitability | NET_INTEREST_INCOME (净利息收入) | 万元 |
| Scale | TOTAL_ASSETS (资产总额) | 万元 |
| Scale | TOTAL_LIABILITIES (负债总额) | 万元 |
| Risk | NPL_RATIO (不良贷款率) | % |
| Risk | CAR_RATIO (资本充足率) | % |
| Business | LOAN_BALANCE (贷款余额) | 万元 |
| Business | DEPOSIT_BALANCE (存款余额) | 万元 |

### Query Dimensions
- **year**: Any year (e.g., 2025)
- **quarter**: 1-4
- **month**: 1-12
- **granularity**: yearly, quarterly, monthly

## 3. Agent Reporting

| Endpoint | Description |
|----------|-------------|
| `POST /agent/report` | Submit client event/action report |

### Report Fields
- `user_id` — User identifier
- `client_ip` — Client IP address
- `mac_address` — Client MAC address
- `os_version` — OS version string
- `app_name` — Application name
- `app_version` — Application version
- `screen_resolution` — Display resolution
- `event_type` — "action" or "event"
- `event_params` — Arbitrary key-value data
- `message_content` — Event description

## 4. Authentication

### Token Types
- **Access Token** — 15-minute validity, RSA-OAEP encrypted
- **Refresh Token** — 7-day validity, supports revocation

### Endpoints
- `POST /mcp/auth/refresh` — Exchange refresh token for access token
- `POST /mcp/auth/revoke` — Revoke a refresh token

## 5. Security

| Mechanism | Description |
|-----------|-------------|
| Token encryption | RSA-OAEP with SHA-256 |
| Metric whitelist | Only predefined metrics allowed |
| Row-Level Security | Users filtered by branch_id |
| Role-Based Access | admin/viewer roles |
| Token revocation | JSON-based blacklist |

## 6. Logging

- Structured log format with MDC context
- Daily log rotation
- Per-service log directories (`/data/logs/<service>/`)
- Access logs and application logs separated
- Trace ID propagation for request tracking
