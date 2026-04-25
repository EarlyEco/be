import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

from app.core.config import settings


def create_db_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(settings.mongodb_uri, tlsCAFile=certifi.where())


def get_database(client: AsyncIOMotorClient):
    return client[settings.mongodb_db_name]


async def ensure_db_indexes(db) -> None:
    await db["users"].create_index([("email", ASCENDING)], unique=True)
    await db["sessions"].create_index([("session_id", ASCENDING)], unique=True)
    await db["sessions"].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)


async def close_db_client(client: AsyncIOMotorClient) -> None:
    client.close()


async def check_db_connection(client: AsyncIOMotorClient) -> bool:
    result = await client.admin.command("ping")
    return result.get("ok") == 1.0
