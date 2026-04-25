from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db import close_db_pool, create_db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await create_db_pool()
    try:
        yield
    finally:
        await close_db_pool(app.state.db_pool)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api/v1")

