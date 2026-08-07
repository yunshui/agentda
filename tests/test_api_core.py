"""
Tests for api-core service.

Tests:
- Health check
- User info query (valid, invalid format, non-existent)
- Admin users list (admin access, invalid user)
- Finance dictionary (mocked FINANCE, 10-min cache)
- Finance query (mocked FINANCE, valid, invalid metric, missing user_id, invalid params, upstream error)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

import httpx


# ==================== Mock FINANCE Service ====================

MOCK_FINANCE_DICTIONARY = {
    "metrics": [
        {
            "standard_name": "1100000",
            "display_name": "营业净收入",
            "category": "盈利能力",
            "unit": "元",
            "description": "利息收入减去利息支出",
            "synonyms": ["利息收入", "息差收入", "净利息"],
        },
        {
            "standard_name": "2100000",
            "display_name": "总资产余額",
            "category": "盈利能力",
            "unit": "元",
            "description": "银行全部资产的总和",
            "synonyms": ["总资产", "资产负债表资产", "资产规模"],
        },
        {
            "standard_name": "2200000",
            "display_name": "总负债余額",
            "category": "规模指标",
            "unit": "元",
            "description": "银行全部负债的总和",
            "synonyms": ["总负债", "负债规模"],
        },
        {
            "standard_name": "1600000",
            "display_name": "税后净利润",
            "category": "规模指标",
            "unit": "元",
            "description": "扣除所有成本、税费后的利润总额",
            "synonyms": ["纯利润", "税后利润", "利润总额", "净利润"],
        },
    ],
    "dimensions": [
        {"name": "year", "display_name": "年份", "type": "int", "required": False},
        {"name": "quarter", "display_name": "季度", "type": "int", "range": "1-4"},
        {"name": "month", "display_name": "月份", "type": "int", "range": "1-12"},
        {"name": "granularity", "display_name": "聚合粒度", "type": "String", "values": ["yearly", "quarterly", "monthly"]},
    ],
}


def _build_query_response(params: dict) -> dict:
    """根据请求参数构造 FINANCE get_t51_amount 响应"""
    return {
        "errorCode": "0",
        "errorMsg": "",
        "metric": params.get("metric", ""),
        "metric_name": "税后净利润",
        "unit": "元",
        "granularity": params.get("granularity", "yearly"),
        "data": [{"period": f"{params.get('year', 2025)}-Q1", "value": "7941798756.74000"}],
        "query_time": "2026-08-03 18:30:34",
    }


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error", request=None, response=self)

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, router, **kwargs):
        self._router = router

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None):
        return self._router(url, params)


def _make_router(overrides=None):
    """创建按完整地址（含 flowActionName）分发的 mock 路由；overrides 用于定制查询响应"""
    counts = {"dictionary": 0, "query": 0}

    def router(url, params):
        if "flowActionName=get_dictionary" in url:
            counts["dictionary"] += 1
            return FakeResponse(MOCK_FINANCE_DICTIONARY)
        if "flowActionName=get_t51_amount" in url:
            counts["query"] += 1
            if overrides:
                resp = _build_query_response(params)
                resp.update(overrides)
                return FakeResponse(resp)
            return FakeResponse(_build_query_response(params))
        return FakeResponse({})

    return router, counts


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def api_app():
    """Import and return the api-core FastAPI app."""
    from conftest import import_service_app
    return import_service_app("api-core")


@pytest.fixture(autouse=True)
def reset_finance_cache():
    """每个测试前重置 FINANCE 字典缓存，避免跨用例相互影响"""
    import finance_client
    finance_client._dict_cache = {"data": None, "fetched_at": 0.0}
    yield


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
        resp = await client.get("/api/user/001001220")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "001001220"
    assert data["name"] == "王礼东"
    assert data["role"] == "admin"
    assert data["department"] == "金融科技部"


@pytest.mark.asyncio
async def test_get_user_second(api_app):
    """GET /api/user/{user_id} for another valid user."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/user/001572026")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "001572026"
    assert data["name"] == "石磊"


@pytest.mark.asyncio
async def test_get_user_invalid_format(api_app):
    """GET /api/user/{user_id} with non-9-digit ID returns 200 + errorCode 400."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/user/12345")
    assert resp.status_code == 200
    assert resp.json()["errorCode"] == "400"
    assert "9位数字" in resp.json()["errorMsg"]


@pytest.mark.asyncio
async def test_get_user_not_found(api_app):
    """GET /api/user/{user_id} with non-existent ID returns 200 + errorCode 404."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/user/999999999")
    assert resp.status_code == 200
    assert resp.json()["errorCode"] == "404"
    assert "不存在" in resp.json()["errorMsg"]


# ==================== Admin: List All Users ====================

@pytest.mark.asyncio
async def test_get_all_users_as_admin(api_app):
    """Admin can list all users."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/001001220/users")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 8
    assert len(data["users"]) == 8
    # Verify key fields are present
    assert all(k in data["users"][0] for k in ("user_id", "name", "department", "role"))


@pytest.mark.asyncio
async def test_get_all_users_invalid_format(api_app):
    """Invalid user ID format returns 200 + errorCode 400."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/12345/users")
    assert resp.status_code == 200
    assert resp.json()["errorCode"] == "400"


@pytest.mark.asyncio
async def test_get_all_users_not_found(api_app):
    """Non-existent user returns 200 + errorCode 404."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/999999999/users")
    assert resp.status_code == 200
    assert resp.json()["errorCode"] == "404"


# ==================== Finance Dictionary ====================

@pytest.mark.asyncio
async def test_get_finance_dictionary(api_app):
    """GET /api/finance/dictionary returns FINANCE dictionary (mocked)."""
    transport = ASGITransport(app=api_app)
    with patch("finance_client.httpx.AsyncClient", lambda *a, **k: FakeAsyncClient(_make_router()[0])):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/finance/dictionary")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    assert "dimensions" in data
    metric_names = {m["standard_name"] for m in data["metrics"]}
    assert "1600000" in metric_names
    assert "1100000" in metric_names
    # Old mock metric names should no longer exist
    assert "NET_PROFIT" not in metric_names


@pytest.mark.asyncio
async def test_finance_dictionary_cached(api_app):
    """Within the 10-min TTL, the dictionary is only fetched once from FINANCE."""
    import finance_client
    finance_client._dict_cache = {"data": None, "fetched_at": 0.0}
    router, counts = _make_router()
    transport = ASGITransport(app=api_app)
    with patch("finance_client.httpx.AsyncClient", lambda *a, **k: FakeAsyncClient(router)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.get("/api/finance/dictionary")
            r2 = await client.get("/api/finance/dictionary")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()
    # Second call served from cache, no extra upstream request
    assert counts["dictionary"] == 1


# ==================== Finance Query ====================

@pytest.mark.asyncio
async def test_finance_query_valid(api_app):
    """Valid finance query returns FINANCE data (mocked)."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "001001220"}
    with patch("finance_client.httpx.AsyncClient", lambda *a, **k: FakeAsyncClient(_make_router()[0])):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/finance/query",
                params={"metric": "1600000", "year": 2025, "granularity": "quarterly"},
                headers=headers
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["errorCode"] == "0"
    assert data["metric"] == "1600000"
    assert data["granularity"] == "quarterly"
    assert data["data"][0]["period"] == "2025-Q1"


@pytest.mark.asyncio
async def test_finance_query_invalid_metric(api_app):
    """Finance query with invalid metric returns 400."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "001001220"}
    with patch("finance_client.httpx.AsyncClient", lambda *a, **k: FakeAsyncClient(_make_router()[0])):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/finance/query",
                params={"metric": "9999999", "granularity": "yearly"},
                headers=headers
            )
    assert resp.status_code == 400
    assert "不支持" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_finance_query_missing_user_id(api_app):
    """Finance query without X-User-ID header returns 200 + errorCode 400."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "1600000", "granularity": "yearly"}
        )
    assert resp.status_code == 200
    assert resp.json()["errorCode"] == "400"
    assert "9位数字" in resp.json()["errorMsg"]


@pytest.mark.asyncio
async def test_finance_query_user_not_found(api_app):
    """Finance query with well-formed but non-existent user returns 200 + errorCode 404."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "999999999"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/finance/query",
            params={"metric": "1600000", "granularity": "yearly"},
            headers=headers
        )
    assert resp.status_code == 200
    assert resp.json()["errorCode"] == "404"
    assert "不存在" in resp.json()["errorMsg"]


@pytest.mark.asyncio
async def test_finance_query_invalid_granularity(api_app):
    """Finance query with invalid granularity returns 400."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "001001220"}
    with patch("finance_client.httpx.AsyncClient", lambda *a, **k: FakeAsyncClient(_make_router()[0])):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/finance/query",
                params={"metric": "1600000", "granularity": "daily"},
                headers=headers
            )
    assert resp.status_code == 400
    assert "granularity" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_finance_query_invalid_quarter(api_app):
    """Finance query with out-of-range quarter returns 400."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "001001220"}
    with patch("finance_client.httpx.AsyncClient", lambda *a, **k: FakeAsyncClient(_make_router()[0])):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/finance/query",
                params={"metric": "1600000", "quarter": 5, "granularity": "quarterly"},
                headers=headers
            )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_finance_query_upstream_error(api_app):
    """FINANCE returns non-zero errorCode -> api-core returns 400 with errorMsg."""
    transport = ASGITransport(app=api_app)
    headers = {"X-User-ID": "001001220"}
    router, _ = _make_router(overrides={"errorCode": "1", "errorMsg": "指标数据不存在"})
    with patch("finance_client.httpx.AsyncClient", lambda *a, **k: FakeAsyncClient(router)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/finance/query",
                params={"metric": "1600000", "granularity": "yearly"},
                headers=headers
            )
    assert resp.status_code == 400
    assert "指标数据不存在" in resp.json()["detail"]
