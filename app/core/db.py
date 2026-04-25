from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings


def create_db_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(settings.mongodb_uri)


def get_database(client: AsyncIOMotorClient):
    return client[settings.mongodb_db_name]


async def close_db_client(client: AsyncIOMotorClient) -> None:
    client.close()


async def check_db_connection(client: AsyncIOMotorClient) -> bool:
    result = await client.admin.command("ping")
    return result.get("ok") == 1.0
