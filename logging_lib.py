"""
Shared logging utilities for Bankda services.

Provides per-request MDC context via ContextVars, daily rotating file handlers,
custom formatting, and an ASGI middleware for automatic access logging.
"""

import logging
import os
import uuid
from contextvars import ContextVar
from datetime import datetime
from copy import copy
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ==================== MDC ContextVars ====================

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
client_ip_var: ContextVar[str] = ContextVar("client_ip", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
method_var: ContextVar[str] = ContextVar("method", default="-")
uri_var: ContextVar[str] = ContextVar("uri", default="-")
status_var: ContextVar[str] = ContextVar("status", default="-")
duration_ms_var: ContextVar[str] = ContextVar("duration_ms", default="-")

# ==================== Configuration ====================

LOG_FORMAT = (
    "%(asctime)s|%(levelname)-5s|%(name)-36s|"
    "%(clientIp)s|%(UserID)s|%(traceId)s|"
    "%(method)s|%(uri)s|%(status)s|%(duration_ms)s|"
    "%(message)s"
)


# ==================== AppFormatter ====================

class AppFormatter(logging.Formatter):
    """
    Custom log formatter.

    - Timestamp formatted as yyyy-MM-dd HH:mm:ss.SSS
    - Logger name left-truncated to 36 characters
    - Newlines in messages replaced with ' | '
    """

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created)
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')}.{int(record.msecs):03d}"

    def format(self, record):
        # Deep-copy to avoid mutating shared record
        record = copy(record)
        # Left-truncate logger name to 36 chars
        if len(record.name) > 36:
            record.name = "..." + record.name[-(36 - 3):]
        # Ensure MDC placeholders exist
        for attr in ("clientIp", "UserID", "traceId", "method", "uri", "status", "duration_ms"):
            if not hasattr(record, attr):
                setattr(record, attr, "-")
        # Format and clean message
        record.message = record.getMessage()
        record.message = record.message.replace("\n", " | ")
        record.asctime = self.formatTime(record)
        return self._fmt % record.__dict__


# ==================== DailyRotatingFileHandler ====================

class DailyRotatingFileHandler(logging.Handler):
    """
    File handler that writes to a new file each day.

    Filename pattern supports {date} placeholder, e.g. "api-{date}.log"
    becomes "api-2026-07-08.log". The logs directory is created automatically.
    """

    def __init__(self, filename_pattern, mode="a", encoding="utf-8", log_dir="logs"):
        super().__init__()
        self.filename_pattern = filename_pattern
        self.mode = mode
        self.encoding = encoding
        self.log_dir = log_dir
        self._file = None
        self._current_date = None
        os.makedirs(self.log_dir, exist_ok=True)
        self._rotate()

    def _get_date_str(self):
        return datetime.now().strftime("%Y-%m-%d")

    def _get_filename(self):
        return os.path.join(self.log_dir, self.filename_pattern.format(date=self._get_date_str()))

    def _rotate(self):
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
        filename = self._get_filename()
        self._file = open(filename, self.mode, encoding=self.encoding)
        self._current_date = self._get_date_str()

    def emit(self, record):
        try:
            if self._get_date_str() != self._current_date:
                self._rotate()
            msg = self.format(record)
            self._file.write(msg + "\n")
            self._file.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
        super().close()


# ==================== MDCFilter ====================

class MDCFilter(logging.Filter):
    """Injects ContextVar values into log record attributes."""

    def filter(self, record):
        record.traceId = trace_id_var.get()
        record.clientIp = client_ip_var.get()
        record.UserID = user_id_var.get()
        record.method = method_var.get()
        record.uri = uri_var.get()
        record.status = status_var.get()
        record.duration_ms = duration_ms_var.get()
        return True


# ==================== setup_logging ====================

def setup_logging(service_name: str, log_dir: str = "logs", access_log_name: str = None):
    """
    Create and configure application + access loggers.

    Args:
        service_name: Short name for the service (e.g. "api", "mcp").
        log_dir: Directory for log files (default "logs").
        access_log_name: Name for the access log file (default f"{service_name}-access").

    Returns:
        Tuple of (app_logger, access_logger).
    """
    if access_log_name is None:
        access_log_name = f"{service_name}-access"

    # --- Application logger ---
    app_logger = logging.getLogger(service_name)
    app_logger.setLevel(logging.INFO)
    app_logger.handlers.clear()

    app_file_handler = DailyRotatingFileHandler(f"{service_name}-{{date}}.log", log_dir=log_dir)
    app_file_handler.setFormatter(AppFormatter(LOG_FORMAT))
    app_file_handler.addFilter(MDCFilter())
    app_logger.addHandler(app_file_handler)

    app_console = logging.StreamHandler()
    app_console.setFormatter(AppFormatter(LOG_FORMAT))
    app_console.addFilter(MDCFilter())
    app_logger.addHandler(app_console)

    # --- Access logger ---
    access_logger = logging.getLogger(f"{service_name}.access")
    access_logger.setLevel(logging.INFO)
    access_logger.handlers.clear()
    access_logger.propagate = False

    access_handler = DailyRotatingFileHandler(f"{access_log_name}-{{date}}.log", log_dir=log_dir)
    access_handler.setFormatter(AppFormatter(LOG_FORMAT))
    access_handler.addFilter(MDCFilter())
    access_logger.addHandler(access_handler)

    return app_logger, access_logger


# ==================== AccessLogMiddleware ====================

class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that logs every request to the access logger.

    - Generates an 8-char hex traceId for each request
    - Captures client IP, HTTP method, URI path
    - Records response status and duration (ms)
    - Skips ``/mcp`` endpoints (MCP handler manages its own access logging)
    """

    def __init__(self, app, app_logger=None, access_logger=None, skip_path_prefix="/mcp"):
        super().__init__(app)
        self.app_logger = app_logger
        self.access_logger = access_logger
        self.skip_path_prefix = skip_path_prefix

    async def dispatch(self, request: Request, call_next):
        # Skip paths matching the configured prefix (MCP handler manages its own access logging)
        if self.skip_path_prefix and request.url.path.startswith(self.skip_path_prefix):
            return await call_next(request)

        trace_id = uuid.uuid4().hex[:8]
        trace_id_var.set(trace_id)
        client_ip_var.set(request.client.host if request.client else "-")
        method_var.set(request.method)
        uri_var.set(request.url.path)

        start = datetime.now()

        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as exc:
            status = 500
            raise
        finally:
            elapsed_ms = int((datetime.now() - start).total_seconds() * 1000)
            status_var.set(str(status))
            duration_ms_var.set(str(elapsed_ms))
            if self.access_logger:
                self.access_logger.info("")
            if self.app_logger:
                self.app_logger.info(
                    "%s %s -> %s (%dms)",
                    request.method,
                    request.url.path,
                    status,
                    elapsed_ms,
                )

        return response
