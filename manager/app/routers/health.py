from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Route, get_db
from ..models import HealthStatus

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=list[HealthStatus])
async def get_health(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Route).order_by(Route.id))
    routes = result.scalars().all()
    return [
        HealthStatus(
            route_id=r.id,
            route_name=r.name,
            target=f"{r.target_host}:{r.target_port}",
            status=r.health_status,
            enabled=r.enabled,
        )
        for r in routes
    ]
