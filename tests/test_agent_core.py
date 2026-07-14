"""
Tests for agent-core service.

Tests:
- Health check endpoint
- Report endpoint with valid data
- Report endpoint validation errors
"""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture(scope="module")
def agent_app():
    """Import and return the agent-core FastAPI app."""
    from conftest import import_service_app
    return import_service_app("agent-core")


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
    """POST /agent/report with valid data should return success."""
    transport = ASGITransport(app=agent_app)
    payload = {
        "user_id": "000000001",
        "client_ip": "192.168.1.1",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "os_version": "Windows 10",
        "app_name": "TestApp",
        "app_version": "1.0.0",
        "screen_resolution": "1920x1080",
        "event_type": "action",
        "event_params": {"key": "value"},
        "message_content": "Test report message"
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/agent/report", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["message"] == "Report received"


@pytest.mark.asyncio
async def test_agent_report_missing_field(agent_app):
    """POST /agent/report missing required field should return 422."""
    transport = ASGITransport(app=agent_app)
    payload = {
        "user_id": "000000001",
        # missing client_ip and other required fields
        "event_type": "action",
        "message_content": "test"
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/agent/report", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agent_report_empty_params(agent_app):
    """POST /agent/report with empty event_params should work."""
    transport = ASGITransport(app=agent_app)
    payload = {
        "user_id": "000000001",
        "client_ip": "10.0.0.1",
        "mac_address": "11:22:33:44:55:66",
        "os_version": "macOS 14",
        "app_name": "TestApp",
        "app_version": "2.0.0",
        "screen_resolution": "2560x1440",
        "event_type": "event",
        "event_params": {},
        "message_content": "Empty params test"
    }
    transport = ASGITransport(app=agent_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/agent/report", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
