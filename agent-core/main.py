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

from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel, Field

from logging_lib import setup_logging, AccessLogMiddleware

app = FastAPI(title="Agent Core")

# Setup logging (no access log bypass — all requests are logged)
app_logger, access_logger = setup_logging("agent-core", access_log_name="agent-acc", log_dir="/data/logs/agent-core")
app.add_middleware(AccessLogMiddleware, app_logger=app_logger, access_logger=access_logger, skip_path_prefix="")


# ==================== Request Model ====================

class ReportRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    client_ip: str = Field(..., description="Client IP address")
    mac_address: str = Field(..., description="Client MAC address")
    os_version: str = Field(..., description="Operating system version")
    app_name: str = Field(..., description="Application name")
    app_version: str = Field(..., description="Application version")
    screen_resolution: str = Field(..., description="Screen resolution")
    event_type: str = Field(..., description="Event type: action or event")
    event_params: dict = Field(default_factory=dict, description="Event parameters")
    message_content: str = Field(..., description="Event message content")


# ==================== Endpoints ====================

@app.post("/agent/report")
async def agent_report(report: ReportRequest):
    """
    Receive and log client event reports.

    Accepts structured event data from client applications,
    logs it, and acknowledges receipt.
    """
    app_logger.info(
        "Agent report: user=%s event=%s app=%s/%s ip=%s",
        report.user_id,
        report.event_type,
        report.app_name,
        report.app_version,
        report.client_ip,
    )
    return {"status": "success", "message": "Report received"}


@app.get("/agent/health")
async def health():
    """Health check"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    app_logger.info("启动 Agent Core 服务, port=8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
