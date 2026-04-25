from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db import close_db_client, create_db_client, get_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_client = create_db_client()
    app.state.db = get_database(app.state.db_client)
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
app.include_router(api_router, prefix="/api/v1")

