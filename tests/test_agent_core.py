"""
Tests for agent-core service.

Tests:
- Health check endpoint
- Report endpoint with valid data (events array format)
- Report endpoint validation errors
- Report endpoint with empty event_params
- Report endpoint with multiple events
"""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture(scope="module")
def agent_app():
    """Import and return the agent-core FastAPI app."""
    from conftest import import_service_app
    return import_service_app("agent-core")


def _valid_payload(events, **overrides):
    """构造符合 ReportRequest 模型的合法请求体。"""
    payload = {
        "user_id": "000000001",
        "client_ip": "192.168.1.1",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "os_version": "Windows 10",
        "app_name": "TestApp",
        "app_version": "1.0.0",
        "screen_resolution": "1920x1080",
        "events": events,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_agent_health(agent_app):
    """GET /agent/health should return ok."""
    transport = ASGITransport(app=agent_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/agent/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_agent_report_valid(agent_app):
    """POST /agent/report with valid events array should return success."""
    transport = ASGITransport(app=agent_app)
    payload = _valid_payload([
        {
            "event_type": "call-llm",
            "event_params": {"key": "value"},
            "message_content": "Test report message",
            "event_time": "2026-08-06 12:00:00.000"
        }
    ])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/agent/report", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["message"] == "1 event(s) received"


@pytest.mark.asyncio
async def test_agent_report_multiple_events(agent_app):
    """POST /agent/report with multiple events should return the event count."""
    transport = ASGITransport(app=agent_app)
    payload = _valid_payload([
        {
            "event_type": "login",
            "event_params": {},
            "message_content": "Login event",
            "event_time": "2026-08-06 12:00:00.000"
        },
        {
            "event_type": "call-mcp",
            "event_params": {"tool": "get_my_info"},
            "message_content": "MCP call",
            "event_time": "2026-08-06 12:00:01.000"
        }
    ])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/agent/report", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["message"] == "2 event(s) received"


@pytest.mark.asyncio
async def test_agent_report_missing_events(agent_app):
    """POST /agent/report missing the required events field should return 422."""
    transport = ASGITransport(app=agent_app)
    payload = {
        "user_id": "000000001",
        "client_ip": "192.168.1.1",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "os_version": "Windows 10",
        "app_name": "TestApp",
        "app_version": "1.0.0",
        "screen_resolution": "1920x1080",
        # missing events array
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/agent/report", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agent_report_empty_params(agent_app):
    """POST /agent/report with empty event_params should work."""
    transport = ASGITransport(app=agent_app)
    payload = _valid_payload([
        {
            "event_type": "call-mcp",
            "event_params": {},
            "message_content": "Empty params test",
            "event_time": "2026-08-06 12:00:00.000"
        }
    ])
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/agent/report", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
