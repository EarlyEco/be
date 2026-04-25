from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import try_load_settings
from app.core.db import close_db_client, create_db_client, ensure_db_indexes, get_database
from app.core.jwt_secret_store import get_or_create_jwt_secret


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = try_load_settings()
    app.state.settings = settings
    app.state.ready = bool(settings)

    if not settings:
        app.state.db_client = None
        app.state.db = None
        app.state.jwt_signing_secret = ""
        app.state.jwt_algorithm = "HS256"
        yield
        return

    app.state.db_client = create_db_client()
    app.state.db = get_database(app.state.db_client)
    await ensure_db_indexes(app.state.db)
    env_secret = os.getenv("JWT_SECRET_KEY")
    if env_secret is not None and env_secret.strip() == "":
        env_secret = None
    app.state.jwt_signing_secret = env_secret or await get_or_create_jwt_secret(app.state.db)
    app.state.jwt_algorithm = settings.jwt_algorithm

    app.title = settings.app_name
    app.version = settings.app_version
    app.debug = settings.debug
    try:
        yield
    finally:
        if app.state.db_client is not None:
            await close_db_client(app.state.db_client)


class MisconfigurationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api") and not getattr(request.app.state, "ready", False):
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Service is not configured. Set MONGODB_URI and MONGODB_DB_NAME in Vercel environment variables (and redeploy).",
                },
            )
        return await call_next(request)


app = FastAPI(lifespan=lifespan)
app.add_middleware(MisconfigurationMiddleware)


@app.get("/", summary="Service status")
def root_status(request: Request):
    settings = getattr(request.app.state, "settings", None)
    if not settings:
        return {
            "status": "misconfigured",
            "message": "Missing MONGODB_URI / MONGODB_DB_NAME. Set them in Vercel env vars.",
        }
    return {"status": "ok", "message": settings.app_name}


app.include_router(api_router, prefix="/api/v1")

