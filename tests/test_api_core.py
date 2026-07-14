"""
Tests for api-core service.

Tests:
- Health check
- User info query (valid, invalid format, non-existent)
- Admin users list (admin access, viewer 403, invalid user)
- Finance dictionary
- Finance query (valid, invalid metric, missing user_id, invalid params, RLS)
"""

import pytest
from httpx import AsyncClient, ASGITransport


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def api_app():
    """Import and return the api-core FastAPI app."""
    from conftest import import_service_app
    return import_service_app("api-core")


# ==================== Health ====================

@pytest.mark.asyncio
async def test_api_health(api_app):
    """GET /api/health should return ok."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ==================== User Info ====================

@pytest.mark.asyncio
async def test_get_user_valid(api_app):
    """GET /api/user/{user_id} with valid ID returns user data."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/user/000000001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "000000001"
    assert data["name"] == "张三"
    assert data["role"] == "admin"
    assert "balance" in data
    assert "department" in data


@pytest.mark.asyncio
async def test_get_user_viewer(api_app):
    """GET /api/user/{user_id} for a viewer user."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/user/000000003")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "000000003"
    assert data["name"] == "王五"
    assert data["role"] == "viewer"


@pytest.mark.asyncio
async def test_get_user_invalid_format(api_app):
    """GET /api/user/{user_id} with non-9-digit ID returns 400."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/user/12345")
    assert resp.status_code == 400
    assert "9位数字" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_user_not_found(api_app):
    """GET /api/user/{user_id} with non-existent ID returns 404."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/user/999999999")
    assert resp.status_code == 404
    assert "不存在" in resp.json()["detail"]


# ==================== Admin: List All Users ====================

@pytest.mark.asyncio
async def test_get_all_users_as_admin(api_app):
    """Admin can list all users."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/000000001/users")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["users"]) == 5
    # Verify balance is NOT in response
    for user in data["users"]:
        assert "balance" not in user
    # Verify key fields are present
    assert all(k in data["users"][0] for k in ("user_id", "name", "department", "role"))


@pytest.mark.asyncio
async def test_get_all_users_as_viewer(api_app):
    """Viewer gets 403 when trying to list users."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/000000003/users")
    assert resp.status_code == 403
    assert "管理员" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_all_users_invalid_format(api_app):
    """Invalid user ID format returns 400."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/12345/users")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_all_users_not_found(api_app):
    """Non-existent user returns 404."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/999999999/users")
    assert resp.status_code == 404


# ==================== Finance Dictionary ====================

@pytest.mark.asyncio
async def test_get_finance_dictionary(api_app):
    """GET /api/finance/dictionary returns metrics metadata."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/finance/dictionary")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "dimensions" in data
    metric_names = {m["standard_name"] for m in data["metrics"]}
    assert "NET_PROFIT" in metric_names
    assert "NPL_RATIO" in metric_names
    assert "TOTAL_ASSETS" in metric_names
    # Verify all 8 metrics are present
    assert len(data["metrics"]) == 8


# ==================== Finance Query ====================

@pytest.mark.asyncio
async def test_finance_query_valid(api_app):
    """Valid finance query returns data."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "000000001"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "NET_PROFIT", "year": 2025, "granularity": "yearly"},
            headers=headers
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric"] == "NET_PROFIT"
    assert data["metric_name"] == "净利润"
    assert data["unit"] == "万元"
    assert data["branch_id"] == "BR001"
    assert len(data["data"]) > 0
    assert data["data"][0]["period"] == "2025"
    assert data["data"][0]["value"] == 125000.00


@pytest.mark.asyncio
async def test_finance_query_no_year(api_app):
    """Finance query without year returns recent data."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "000000001"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "NET_PROFIT", "granularity": "yearly"},
            headers=headers
        )
    assert resp.status_code == 200
    data = resp.json()
    # Should return last 3 years trend data
    assert len(data["data"]) == 3


@pytest.mark.asyncio
async def test_finance_query_quarterly(api_app):
    """Finance query with quarterly granularity."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "000000001"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "NPL_RATIO", "year": 2025, "granularity": "quarterly"},
            headers=headers
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 4
    assert data["data"][0]["period"] == "2025-Q1"


@pytest.mark.asyncio
async def test_finance_query_monthly(api_app):
    """Finance query with monthly granularity."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "000000001"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "LOAN_BALANCE", "year": 2025, "granularity": "monthly"},
            headers=headers
        )
    assert resp.status_code == 200
    data = resp.json()
    # Q3 has None value for 2026, but for 2025 all quarters have data
    assert len(data["data"]) == 12


@pytest.mark.asyncio
async def test_finance_query_specific_quarter(api_app):
    """Finance query with specific quarter."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "000000001"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "NET_PROFIT", "year": 2025, "quarter": 2, "granularity": "quarterly"},
            headers=headers
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["period"] == "2025-Q2"
    assert data["data"][0]["value"] == 32000.00


@pytest.mark.asyncio
async def test_finance_query_invalid_metric(api_app):
    """Finance query with invalid metric returns 400."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "000000001"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "INVALID_METRIC", "granularity": "yearly"},
            headers=headers
        )
    assert resp.status_code == 400
    assert "不支持" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_finance_query_missing_user_id(api_app):
    """Finance query without X-User-ID header returns 400."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "NET_PROFIT", "granularity": "yearly"}
        )
    assert resp.status_code == 400
    assert "格式错误" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_finance_query_invalid_granularity(api_app):
    """Finance query with invalid granularity returns 400."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "000000001"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "NET_PROFIT", "granularity": "daily"},
            headers=headers
        )
    assert resp.status_code == 400
    assert "granularity" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_finance_query_invalid_quarter(api_app):
    """Finance query with out-of-range quarter returns 400."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "000000001"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "NET_PROFIT", "quarter": 5, "granularity": "quarterly"},
            headers=headers
        )
    assert resp.status_code == 400


# ==================== RLS Tests ====================

@pytest.mark.asyncio
async def test_rls_different_branch_returns_different_data(api_app):
    """RLS: Users from different branches see different data."""
    transport = ASGITransport(app=api_app)
    headers_br001 = {"X-User-ID": "000000001"}  # BR001
    headers_br002 = {"X-User-ID": "000000003"}  # BR002

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_br001 = await client.get(
            "/api/finance/query",
            params={"metric": "NET_PROFIT", "year": 2025, "granularity": "yearly"},
            headers=headers_br001
        )
        resp_br002 = await client.get(
            "/api/finance/query",
            params={"metric": "NET_PROFIT", "year": 2025, "granularity": "yearly"},
            headers=headers_br002
        )

    assert resp_br001.status_code == 200
    assert resp_br002.status_code == 200

    data_br001 = resp_br001.json()
    data_br002 = resp_br002.json()

    assert data_br001["branch_id"] == "BR001"
    assert data_br002["branch_id"] == "BR002"

    # Same metric but different branches should have different values
    assert data_br001["data"] != data_br002["data"]
    # BR001 net profit in 2025: 125000, BR002: 102000
    assert data_br001["data"][0]["value"] == 125000.00
    assert data_br002["data"][0]["value"] == 102000.00


@pytest.mark.asyncio
async def test_rls_same_branch_same_data(api_app):
    """RLS: Users from same branch see the same data."""
    transport = ASGITransport(app=api_app)
    headers_user1 = {"X-User-ID": "000000001"}  # BR001, admin
    headers_user2 = {"X-User-ID": "000000002"}  # BR001, admin

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.get(
            "/api/finance/query",
            params={"metric": "NPL_RATIO", "year": 2025, "granularity": "yearly"},
            headers=headers_user1
        )
        resp2 = await client.get(
            "/api/finance/query",
            params={"metric": "NPL_RATIO", "year": 2025, "granularity": "yearly"},
            headers=headers_user2
        )

    assert resp1.json()["data"] == resp2.json()["data"]
    assert resp1.json()["branch_id"] == "BR001"
    assert resp2.json()["branch_id"] == "BR001"
