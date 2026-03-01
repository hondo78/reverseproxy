import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("access")

MAX_LOG_ENTRIES = 1000

PROXY_LOG_FILE = "/data/logs/proxy-access.log"
MANAGER_LOG_FILE = "/data/logs/manager-access.log"

# In-memory buffers for fast API access
proxy_log: deque[dict] = deque(maxlen=MAX_LOG_ENTRIES)
manager_log: deque[dict] = deque(maxlen=MAX_LOG_ENTRIES)

# Track file read position to only read new lines
_proxy_log_pos = 0


def _init_logs():
    os.makedirs("/data/logs", exist_ok=True)

    # Load existing manager log entries
    if os.path.exists(MANAGER_LOG_FILE):
        try:
            with open(MANAGER_LOG_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        manager_log.append(json.loads(line))
        except Exception:
            pass


_init_logs()


def read_new_proxy_lines():
    """Read new lines from the nginx proxy access log."""
    global _proxy_log_pos
    if not os.path.exists(PROXY_LOG_FILE):
        return

    try:
        file_size = os.path.getsize(PROXY_LOG_FILE)
        # Log was rotated / truncated
        if file_size < _proxy_log_pos:
            _proxy_log_pos = 0

        with open(PROXY_LOG_FILE, "r") as f:
            f.seek(_proxy_log_pos)
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        proxy_log.append(entry)
                    except json.JSONDecodeError:
                        pass
            _proxy_log_pos = f.tell()
    except Exception:
        logger.exception("Failed to read proxy access log")


def _append_manager_log(entry: dict):
    try:
        with open(MANAGER_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        client_ip = request.client.host if request.client else "-"
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""
        status = response.status_code
        user_agent = request.headers.get("user-agent", "-")

        # Skip the log endpoints to avoid noise
        if path.startswith("/api/logs"):
            return response

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "client_ip": client_ip,
            "method": method,
            "path": path,
            "query": query,
            "status": status,
            "duration_ms": duration_ms,
            "user_agent": user_agent,
        }

        manager_log.append(entry)
        _append_manager_log(entry)
        logger.info(
            '%s - %s %s%s %s %.1fms "%s"',
            client_ip, method, path,
            f"?{query}" if query else "",
            status, duration_ms, user_agent,
        )

        return response
