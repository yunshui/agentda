# Testing

## Manual Testing

### Health Checks

```bash
# Agent Core (port 8000)
curl http://localhost:8000/agent/health
# → {"status":"ok"}

# MCP Core (port 8001)
curl http://localhost:8001/mcp/health
# → {"status":"ok"}

# API Core (port 8002)
curl http://localhost:8002/api/health
# → {"status":"ok"}
```

### Agent Report

```bash
curl -X POST http://localhost:8000/agent/report \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test001",
    "client_ip": "192.168.1.100",
    "mac_address": "00:1A:2B:3C:4D:5E",
    "os_version": "Windows 10",
    "app_name": "AgentdaClient",
    "app_version": "1.0.0",
    "screen_resolution": "1920x1080",
    "event_type": "action",
    "event_params": {"page": "dashboard"},
    "message_content": "User viewed dashboard"
  }'
# → {"status":"success","message":"Report received"}
```

### User API (via API Core)

> 用户编号取自 `config/users.json`（真实用户数据，不在此处展示）。以下示例使用占位编号 `000000000`，实际调用时请替换为有效用户。

```bash
# Get user info
curl http://localhost:8002/api/user/000000000
# → 有效用户: {"user_id":"...","name":"...","department":"...","role":"..."}
# → 用户不存在: {"errorCode":"404","errorMsg":"用户不存在"}

# List all users (admin only)
curl http://localhost:8002/api/admin/000000000/users
```

### Financial Queries

```bash
# Get dictionary
curl http://localhost:8002/api/finance/dictionary

# Query metric
curl "http://localhost:8002/api/finance/query?metric=NET_PROFIT&year=2025&granularity=yearly" \
  -H "X-User-ID: 000000000"
```

### MCP Protocol

```bash
# List tools
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Call tool
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_my_info","arguments":{}}}'
```

### Token Refresh

```bash
curl -X POST http://localhost:8001/mcp/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<your-refresh-token>"}'
```

## Verification Checklist

After deployment:

- [ ] All three services start without errors
- [ ] Health endpoints return 200 OK
- [ ] Agent report endpoint accepts and logs data
- [ ] Token refresh works (returns new access token)
- [ ] MCP tools list returns 6 tools
- [ ] Financial queries return data from the FINANCE service
- [ ] Admin-only endpoints reject viewer users
- [ ] Log files created in correct directories
- [ ] Docker containers start and stay running
