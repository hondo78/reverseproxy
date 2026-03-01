from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import Route, get_db
from ..models import RouteCreate, RouteResponse, RouteUpdate
from ..services.nginx import apply_config

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.get("", response_model=list[RouteResponse])
async def list_routes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Route).order_by(Route.id))
    return result.scalars().all()


@router.post("", response_model=RouteResponse, status_code=201)
async def create_route(route: RouteCreate, db: AsyncSession = Depends(get_db)):
    if route.route_type not in ("path", "host"):
        raise HTTPException(400, "route_type must be 'path' or 'host'")

    db_route = Route(**route.model_dump())
    db.add(db_route)
    await db.commit()
    await db.refresh(db_route)

    success, msg = await apply_config(db)
    if not success:
        # Route is saved but nginx config failed - still return the route
        db_route.health_status = f"config_error: {msg}"
        await db.commit()

    return db_route


@router.get("/{route_id}", response_model=RouteResponse)
async def get_route(route_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(404, "Route not found")
    return route


@router.put("/{route_id}", response_model=RouteResponse)
async def update_route(route_id: int, update: RouteUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(404, "Route not found")

    update_data = update.model_dump(exclude_unset=True)
    if "route_type" in update_data and update_data["route_type"] not in ("path", "host"):
        raise HTTPException(400, "route_type must be 'path' or 'host'")

    for key, value in update_data.items():
        setattr(route, key, value)

    await db.commit()
    await db.refresh(route)

    success, msg = await apply_config(db)
    if not success:
        route.health_status = f"config_error: {msg}"
        await db.commit()

    return route


@router.delete("/{route_id}")
async def delete_route(route_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(404, "Route not found")

    await db.delete(route)
    await db.commit()

    await apply_config(db)
    return {"detail": "Route deleted"}


@router.post("/{route_id}/toggle", response_model=RouteResponse)
async def toggle_route(route_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(404, "Route not found")

    route.enabled = not route.enabled
    await db.commit()
    await db.refresh(route)

    await apply_config(db)
    return route
