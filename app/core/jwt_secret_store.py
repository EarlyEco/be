import secrets

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError


async def ensure_jwt_secret_indexes(db) -> None:
    await db["app_secrets"].create_index([("key", ASCENDING)], unique=True)


async def get_or_create_jwt_secret(db) -> str:
    collection = db["app_secrets"]
    existing = await collection.find_one({"key": "jwt_hs256_secret"})
    if existing and existing.get("value"):
        return str(existing["value"])

    candidate = secrets.token_urlsafe(48)
    try:
        await collection.insert_one({"key": "jwt_hs256_secret", "value": candidate})
        return candidate
    except DuplicateKeyError:
        existing = await collection.find_one({"key": "jwt_hs256_secret"})
        if not existing or not existing.get("value"):
            raise RuntimeError("Failed to initialize JWT signing secret") from None
        return str(existing["value"])
