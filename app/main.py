from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.db import close_db_client, create_db_client, ensure_db_indexes, get_database

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_client = create_db_client()
    app.state.db = get_database(app.state.db_client)
    await ensure_db_indexes(app.state.db)
    try:
        yield
    finally:
        await close_db_client(app.state.db_client)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)


@app.get("/", summary="Service status")
def root_status() -> dict[str, str]:
    return {"status": "ok", "message": settings.app_name}


app.include_router(api_router, prefix="/api/v1")

