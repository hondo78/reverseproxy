import asyncio
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import HEALTH_CHECK_INTERVAL
from ..database import Route, async_session

logger = logging.getLogger(__name__)


async def check_backend(host: str, port: int) -> str:
    """Check if a backend is reachable via HTTP, falling back to TCP."""
    # Try HTTP first
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"http://{host}:{port}/")
            if resp.status_code < 500:
                return "healthy"
            return "unhealthy"
    except Exception:
        pass

    # Fall back to TCP connect
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=5.0
        )
        writer.close()
        await writer.wait_closed()
        return "healthy"
    except Exception:
        return "unreachable"


async def check_all_backends() -> None:
    """Check health of all enabled routes and update status in DB."""
    async with async_session() as db:
        result = await db.execute(select(Route).where(Route.enabled.is_(True)))
        routes = result.scalars().all()

        for route in routes:
            status = await check_backend(route.target_host, route.target_port)
            route.health_status = status

        await db.commit()


async def health_check_loop() -> None:
    """Periodically check all backends."""
    while True:
        try:
            await check_all_backends()
        except Exception:
            logger.exception("Health check cycle failed")
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
