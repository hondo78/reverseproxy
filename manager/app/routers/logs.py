from datetime import datetime, timezone

from fastapi import APIRouter, Query

from ..middleware import manager_log, proxy_log, read_new_proxy_lines

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _filter_entries(
    entries: list[dict],
    limit: int,
    ip: str | None,
    method: str | None,
    path: str | None,
    time_from: str | None,
    time_to: str | None,
) -> list[dict]:
    result = entries

    if ip:
        ip_lower = ip.lower()
        result = [e for e in result if ip_lower in e.get("client_ip", "").lower()]

    if method:
        method_upper = method.upper()
        result = [e for e in result if e.get("method", "").upper() == method_upper]

    if path:
        path_lower = path.lower()
        result = [
            e for e in result
            if path_lower in e.get("path", "").lower()
            or path_lower in e.get("server_name", "").lower()
        ]

    if time_from:
        try:
            dt_from = datetime.fromisoformat(time_from).replace(tzinfo=timezone.utc)
            result = [
                e for e in result
                if datetime.fromisoformat(e["timestamp"]).replace(tzinfo=timezone.utc) >= dt_from
            ]
        except ValueError:
            pass

    if time_to:
        try:
            dt_to = datetime.fromisoformat(time_to).replace(tzinfo=timezone.utc)
            result = [
                e for e in result
                if datetime.fromisoformat(e["timestamp"]).replace(tzinfo=timezone.utc) <= dt_to
            ]
        except ValueError:
            pass

    return result[-limit:]


@router.get("/proxy")
async def get_proxy_logs(
    limit: int = Query(200, ge=1, le=1000),
    ip: str | None = Query(None),
    method: str | None = Query(None),
    path: str | None = Query(None),
    time_from: str | None = Query(None),
    time_to: str | None = Query(None),
):
    """Access logs from the Nginx reverse proxy (traffic to backends)."""
    read_new_proxy_lines()
    return _filter_entries(list(proxy_log), limit, ip, method, path, time_from, time_to)


@router.get("/manager")
async def get_manager_logs(
    limit: int = Query(200, ge=1, le=1000),
    ip: str | None = Query(None),
    method: str | None = Query(None),
    path: str | None = Query(None),
    time_from: str | None = Query(None),
    time_to: str | None = Query(None),
):
    """Access logs from the Manager API/UI."""
    return _filter_entries(list(manager_log), limit, ip, method, path, time_from, time_to)
