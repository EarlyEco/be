from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.db import close_db_client, create_db_client, ensure_db_indexes, get_database
from app.core.jwt_secret_store import get_or_create_jwt_secret

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_client = create_db_client()
    app.state.db = get_database(app.state.db_client)
    await ensure_db_indexes(app.state.db)
    env_secret = os.getenv("JWT_SECRET_KEY")
    if env_secret is not None and env_secret.strip() == "":
        env_secret = None
    app.state.jwt_signing_secret = env_secret or await get_or_create_jwt_secret(app.state.db)
    app.state.jwt_algorithm = settings.jwt_algorithm
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

