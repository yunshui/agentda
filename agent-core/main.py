"""
Agent Core Service

Provides client reporting endpoint for tracking user actions and events.
Accepts structured event data and logs it for downstream processing.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path so logging_lib is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel, Field

from logging_lib import setup_logging, AccessLogMiddleware

app = FastAPI(title="Agent Core")

# Setup logging (no access log bypass — all requests are logged)
app_logger, access_logger = setup_logging("agent-core", access_log_name="agent-acc", log_dir="/data/logs/agent-core")
app.add_middleware(AccessLogMiddleware, app_logger=app_logger, access_logger=access_logger)


# ==================== Request Model ====================

class ReportItem(BaseModel):
    event_type: str = Field(..., description="Event type, e.g. login, call-skills, call-mcp, call-llm")
    event_params: dict = Field(default_factory=dict, description="Event parameters")
    message_content: str = Field(..., description="Event message content")
    event_time: str = Field(..., description="Event occurrence time (yyyy-MM-dd HH:mm:ss.SSS)")


class ReportRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    client_ip: str = Field(..., description="Client IP address")
    mac_address: str = Field(..., description="Client MAC address")
    os_version: str = Field(..., description="Operating system version")
    app_name: str = Field(..., description="Application name")
    app_version: str = Field(..., description="Application version")
    screen_resolution: str = Field(..., description="Screen resolution")
    events: list[ReportItem] = Field(..., description="List of event/action items")


# ==================== Endpoints ====================

@app.post("/agent/report")
async def agent_report(report: ReportRequest):
    """
    Receive and log client event reports in batch.

    Accepts a list of structured events from client applications,
    logs each event individually with shared client context.
    """
    count = len(report.events)
    now = datetime.now()
    systime = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"
    for i, item in enumerate(report.events, 1):
        app_logger.info(
            "%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s",
            systime,
            report.user_id,
            report.client_ip,
            report.mac_address,
            report.os_version,
            report.app_name,
            report.app_version,
            report.screen_resolution,
            item.event_time,
            item.event_type,
            item.event_params,
            item.message_content,
        )
    return {"status": "success", "message": f"{count} event(s) received"}


@app.get("/agent/health")
async def health():
    """Health check"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    app_logger.info("启动 Agent Core 服务, port=8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
