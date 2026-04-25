import asyncpg
from asyncpg import Pool
from asyncpg.exceptions import InvalidCatalogNameError

from app.core.config import settings


def _quote_identifier(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


async def _ensure_database_exists() -> None:
    admin_connection = await asyncpg.connect(
        host=settings.database_host,
        port=settings.database_port,
        user=settings.database_username,
        password=settings.database_password,
        database="postgres",
    )
    try:
        exists = await admin_connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1;",
            settings.database_name,
        )
        if not exists:
            database_name = _quote_identifier(settings.database_name)
            await admin_connection.execute(f"CREATE DATABASE {database_name};")
    finally:
        await admin_connection.close()


async def create_db_pool() -> Pool:
    try:
        return await asyncpg.create_pool(dsn=settings.database_dsn, min_size=1, max_size=5)
    except InvalidCatalogNameError:
        await _ensure_database_exists()
        return await asyncpg.create_pool(dsn=settings.database_dsn, min_size=1, max_size=5)


async def close_db_pool(pool: Pool) -> None:
    await pool.close()


async def check_db_connection(pool: Pool) -> bool:
    async with pool.acquire() as connection:
        result = await connection.fetchval("SELECT 1;")
        return result == 1
