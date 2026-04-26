import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from app.core.config import get_settings
from app.core.jwt_secret_store import ensure_jwt_secret_indexes


def create_db_client() -> AsyncIOMotorClient:
    settings = get_settings()
    return AsyncIOMotorClient(settings.mongodb_uri, tlsCAFile=certifi.where())


def get_database(client: AsyncIOMotorClient):
    settings = get_settings()
    return client[settings.mongodb_db_name]


async def ensure_db_indexes(db) -> None:
    await db["users"].create_index([("email", ASCENDING)], unique=True)
    await db["sessions"].create_index([("session_id", ASCENDING)], unique=True)
    await db["sessions"].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    await db["health_checkins"].create_index([("user_id", ASCENDING), ("recorded_at", DESCENDING)])
    await db["health_checkins"].create_index([("city", ASCENDING), ("recorded_at", DESCENDING)])
    await db["health_checkins"].create_index([("latitude", ASCENDING), ("longitude", ASCENDING), ("recorded_at", DESCENDING)])
    await ensure_jwt_secret_indexes(db)


async def close_db_client(client: AsyncIOMotorClient) -> None:
    client.close()


async def check_db_connection(client: AsyncIOMotorClient) -> bool:
    result = await client.admin.command("ping")
    return result.get("ok") == 1.0
