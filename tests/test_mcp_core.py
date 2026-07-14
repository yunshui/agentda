"""
Tests for mcp-core service.

Tests:
- Health check
- Token refresh (valid/invalid token)
- Token revocation
- MCP endpoint authentication
- MCP tools/list (with auth, without auth)
- MCP tools/call (with mocked backend API)
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, Mock
import httpx
from httpx import AsyncClient, ASGITransport


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def mcp_app():
    """Import and return the mcp-core FastAPI app."""
    from conftest import import_service_app
    return import_service_app("mcp-core")


MOCK_USER_RESPONSE = {
    "user_id": "000000001",
    "name": "张三",
    "department": "财务部",
    "role": "admin",
    "balance": 125000.00
}

MOCK_USERS_LIST_RESPONSE = {
    "total": 5,
    "users": [
        {"user_id": "000000001", "name": "张三", "department": "财务部", "role": "admin"},
        {"user_id": "000000002", "name": "李四", "department": "财务部", "role": "admin"},
        {"user_id": "000000003", "name": "王五", "department": "技术部", "role": "viewer"},
    ]
}

MOCK_FINANCE_DICT_RESPONSE = {
    "metrics": [
        {"standard_name": "NET_PROFIT", "display_name": "净利润", "category": "盈利能力", "unit": "万元"}
    ],
    "dimensions": []
}

MOCK_FINANCE_QUERY_RESPONSE = {
    "metric": "NET_PROFIT",
    "metric_name": "净利润",
    "unit": "万元",
    "branch_id": "BR001",
    "granularity": "yearly",
    "data": [{"period": "2025", "value": 125000.00}]
}


def _make_mock_response(status_code: int, json_data: dict):
    """Create a mock httpx.Response with sync methods."""
    mock_resp = AsyncMock()
    mock_resp.status_code = status_code
    # httpx.Response.json() and raise_for_status() are synchronous
    mock_resp.json = Mock(return_value=json_data)
    mock_resp.raise_for_status = Mock() if status_code < 400 else Mock(side_effect=httpx.HTTPStatusError("Error", request=Mock(), response=mock_resp))
    return mock_resp


def _mock_async_client_get(url: str, **kwargs):
    """Helper to create mocked httpx response based on URL pattern."""
    if "/api/user/" in url:
        return _make_mock_response(200, MOCK_USER_RESPONSE)
    elif "/api/admin/" in url:
        return _make_mock_response(200, MOCK_USERS_LIST_RESPONSE)
    elif "/api/finance/dictionary" in url:
        return _make_mock_response(200, MOCK_FINANCE_DICT_RESPONSE)
    elif "/api/finance/query" in url:
        return _make_mock_response(200, MOCK_FINANCE_QUERY_RESPONSE)
    else:
        return _make_mock_response(200, {})


# ==================== Health ====================

@pytest.mark.asyncio
async def test_mcp_health(mcp_app):
    """GET /mcp/health should return ok."""
    transport = ASGITransport(app=mcp_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/mcp/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ==================== Token Refresh ====================

@pytest.mark.asyncio
async def test_refresh_token_valid(mcp_app, refresh_token):
    """POST /mcp/auth/refresh with valid refresh token returns access token."""
    token_str, token_data = refresh_token
    transport = ASGITransport(app=mcp_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp/auth/refresh",
            json={"refresh_token": token_str}
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["expires_in"] == 900  # 15 min * 60


@pytest.mark.asyncio
async def test_refresh_token_missing(mcp_app):
    """POST /mcp/auth/refresh without refresh_token returns 400."""
    transport = ASGITransport(app=mcp_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp/auth/refresh",
            json={}
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refresh_token_invalid(mcp_app):
    """POST /mcp/auth/refresh with invalid token returns 401."""
    transport = ASGITransport(app=mcp_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp/auth/refresh",
            json={"refresh_token": "invalid_token_string"}
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_expired(mcp_app, expired_access_token):
    """POST /mcp/auth/refresh with expired access token (used as refresh) returns 401."""
    transport = ASGITransport(app=mcp_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp/auth/refresh",
            json={"refresh_token": expired_access_token}
        )
    assert resp.status_code == 401


# ==================== Token Revocation ====================

@pytest.mark.asyncio
async def test_revoke_token(mcp_app, refresh_token):
    """POST /mcp/auth/revoke should mark token as revoked."""
    _, token_data = refresh_token
    jti = token_data["jti"]

    transport = ASGITransport(app=mcp_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp/auth/revoke",
            json={"jti": jti}
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "revoked"


@pytest.mark.asyncio
async def test_revoke_token_missing_jti(mcp_app):
    """POST /mcp/auth/revoke without jti returns 400."""
    transport = ASGITransport(app=mcp_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp/auth/revoke",
            json={}
        )
    assert resp.status_code == 400


# ==================== MCP Endpoint (no auth) ====================

@pytest.mark.asyncio
async def test_mcp_no_auth(mcp_app):
    """POST /mcp without auth header returns 401."""
    transport = ASGITransport(app=mcp_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        )
    assert resp.status_code == 401


# ==================== MCP tools/list ====================

@pytest.mark.asyncio
async def test_mcp_tools_list(mcp_app, access_token):
    """POST /mcp with valid auth and tools/list returns tool list."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers=headers
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data
    assert "tools" in data["result"]
    tool_names = {t["name"] for t in data["result"]["tools"]}
    assert "get_my_info" in tool_names
    assert "get_my_balance" in tool_names
    assert "get_my_department" in tool_names
    assert "check_my_permission" in tool_names
    assert "list_all_users" in tool_names
    assert "get_finance_dictionary" in tool_names
    assert "query_financial_metrics" in tool_names


# ==================== MCP tools/call ====================

@pytest.mark.asyncio
async def test_mcp_get_my_info(mcp_app, access_token):
    """Call get_my_info tool via MCP."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_mock_async_client_get)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "get_my_info", "arguments": {}},
                    "id": 2
                },
                headers=headers
            )

    assert resp.status_code == 200
    result = resp.json()
    assert "result" in result
    content_text = result["result"]["content"][0]["text"]
    assert "000000001" in content_text
    assert "张三" in content_text


@pytest.mark.asyncio
async def test_mcp_get_my_balance(mcp_app, access_token):
    """Call get_my_balance tool via MCP."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_mock_async_client_get)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "get_my_balance", "arguments": {}},
                    "id": 3
                },
                headers=headers
            )

    assert resp.status_code == 200
    result = resp.json()
    content_text = result["result"]["content"][0]["text"]
    assert "125000.0" in content_text


@pytest.mark.asyncio
async def test_mcp_get_my_department(mcp_app, access_token):
    """Call get_my_department tool via MCP."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_mock_async_client_get)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "get_my_department", "arguments": {}},
                    "id": 4
                },
                headers=headers
            )

    assert resp.status_code == 200
    result = resp.json()
    content_text = result["result"]["content"][0]["text"]
    assert "财务部" in content_text


@pytest.mark.asyncio
async def test_mcp_check_my_permission(mcp_app, access_token):
    """Call check_my_permission tool via MCP."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_mock_async_client_get)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "check_my_permission", "arguments": {}},
                    "id": 5
                },
                headers=headers
            )

    assert resp.status_code == 200
    result = resp.json()
    content_text = result["result"]["content"][0]["text"]
    assert "admin" in content_text


@pytest.mark.asyncio
async def test_mcp_list_all_users(mcp_app, access_token):
    """Call list_all_users tool via MCP."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_mock_async_client_get)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "list_all_users", "arguments": {}},
                    "id": 6
                },
                headers=headers
            )

    assert resp.status_code == 200
    result = resp.json()
    content_text = result["result"]["content"][0]["text"]
    assert "total" in content_text


@pytest.mark.asyncio
async def test_mcp_get_finance_dictionary(mcp_app, access_token):
    """Call get_finance_dictionary tool via MCP."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_mock_async_client_get)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "get_finance_dictionary", "arguments": {}},
                    "id": 7
                },
                headers=headers
            )

    assert resp.status_code == 200
    result = resp.json()
    content_text = result["result"]["content"][0]["text"]
    assert "NET_PROFIT" in content_text


@pytest.mark.asyncio
async def test_mcp_query_financial_metrics(mcp_app, access_token):
    """Call query_financial_metrics tool via MCP."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=_mock_async_client_get)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "query_financial_metrics",
                        "arguments": {
                            "metric": "NET_PROFIT",
                            "year": 2025,
                            "granularity": "yearly"
                        }
                    },
                    "id": 8
                },
                headers=headers
            )

    assert resp.status_code == 200
    result = resp.json()
    content_text = result["result"]["content"][0]["text"]
    assert "NET_PROFIT" in content_text


# ==================== MCP initialize ====================

@pytest.mark.asyncio
async def test_mcp_initialize(mcp_app, access_token):
    """MCP initialize request returns protocol info."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 9
            },
            headers=headers
        )
    assert resp.status_code == 200
    result = resp.json()
    assert result["result"]["protocolVersion"] == "2024-11-05"
    assert result["result"]["serverInfo"]["name"] == "FinanceService"


# ==================== MCP ping ====================

@pytest.mark.asyncio
async def test_mcp_ping(mcp_app, access_token):
    """MCP ping request returns ok."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token}"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "ping",
                "id": 10
            },
            headers=headers
        )
    assert resp.status_code == 200
    assert resp.json()["result"] == {}


# ==================== viewer permission ====================

@pytest.mark.asyncio
async def test_mcp_viewer_permission(mcp_app, access_token_viewer):
    """Viewer can call their own info but not list_all_users."""
    transport = ASGITransport(app=mcp_app)
    headers = {"Authorization": f"Bearer {access_token_viewer}"}

    def mock_viewer_response(url: str, **kwargs):
        if "/api/admin/" in url:
            return _make_mock_response(403, {"detail": "需要管理员权限"})
        elif "/api/user/" in url:
            return _make_mock_response(200, {
                "user_id": "000000003",
                "name": "王五",
                "department": "技术部",
                "role": "viewer",
                "balance": 88000.00
            })
        return _make_mock_response(200, {})

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=mock_viewer_response)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Viewer can get own info
            resp_info = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "get_my_info", "arguments": {}},
                    "id": 11
                },
                headers=headers
            )
            # Viewer cannot list all users
            resp_list = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "list_all_users", "arguments": {}},
                    "id": 12
                },
                headers=headers
            )

    assert resp_info.status_code == 200
    info_text = resp_info.json()["result"]["content"][0]["text"]
    assert "王五" in info_text

    assert resp_list.status_code == 200
    list_text = resp_list.json()["result"]["content"][0]["text"]
    assert "403" in list_text or "需要管理员权限" in list_text
