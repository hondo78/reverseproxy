import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .middleware import AccessLogMiddleware
from .routers import certificates, health, logs, routes
from .services.healthcheck import health_check_loop
from .services.nginx import generate_default_cert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await generate_default_cert()
    health_task = asyncio.create_task(health_check_loop())
    yield
    # Shutdown
    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Reverse Proxy Manager", version="1.0.0", lifespan=lifespan)

app.add_middleware(AccessLogMiddleware)

app.include_router(routes.router)
app.include_router(certificates.router)
app.include_router(health.router)
app.include_router(logs.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
