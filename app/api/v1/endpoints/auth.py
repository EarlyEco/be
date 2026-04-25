from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies.auth import get_current_user
from app.core.config import get_settings
from app.core.security import (
    build_session_expiry,
    create_access_token,
    hash_password,
    new_session_id,
    verify_password,
)
from app.schemas.auth import AuthTokenResponse, SignInRequest, SignUpRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignUpRequest, request: Request) -> AuthTokenResponse:
    settings = get_settings()
    users_collection = request.app.state.db["users"]
    sessions_collection = request.app.state.db["sessions"]

    existing_user = await users_collection.find_one({"email": payload.email.lower()})
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    now = datetime.now(timezone.utc)
    user_data = {
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "full_name": payload.full_name.strip(),
        "created_at": now,
        "updated_at": now,
    }
    insert_result = await users_collection.insert_one(user_data)
    user_id = str(insert_result.inserted_id)

    session_id = new_session_id()
    expires_at = build_session_expiry()
    await sessions_collection.insert_one(
        {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now,
            "last_activity_at": now,
            "expires_at": expires_at,
        }
    )

    try:
        token = create_access_token(user_id=user_id, session_id=session_id, expires_at=expires_at)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server is missing JWT_SECRET_KEY configuration",
        ) from exc
    return AuthTokenResponse(
        access_token=token,
        expires_in_seconds=settings.session_timeout_minutes * 60,
    )


@router.post("/signin", response_model=AuthTokenResponse)
async def signin(payload: SignInRequest, request: Request) -> AuthTokenResponse:
    settings = get_settings()
    users_collection = request.app.state.db["users"]
    sessions_collection = request.app.state.db["sessions"]

    user = await users_collection.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    now = datetime.now(timezone.utc)
    session_id = new_session_id()
    expires_at = build_session_expiry()
    await sessions_collection.insert_one(
        {
            "session_id": session_id,
            "user_id": str(user["_id"]),
            "created_at": now,
            "last_activity_at": now,
            "expires_at": expires_at,
        }
    )

    try:
        token = create_access_token(
            user_id=str(user["_id"]),
            session_id=session_id,
            expires_at=expires_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server is missing JWT_SECRET_KEY configuration",
        ) from exc
    return AuthTokenResponse(
        access_token=token,
        expires_in_seconds=settings.session_timeout_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=str(current_user["_id"]) if isinstance(current_user.get("_id"), ObjectId) else current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
    )
