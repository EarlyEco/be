from fastapi import APIRouter, Request

from app.core.db import check_db_connection

router = APIRouter()


@router.get("/health", summary="Health check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db", summary="Database health check")
async def database_health_check(request: Request) -> dict[str, str]:
    db_ok = await check_db_connection(request.app.state.db_client)
    return {"status": "ok" if db_ok else "error"}
