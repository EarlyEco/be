from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies.auth import get_current_user
from app.core.security import (
    build_session_expiry,
    create_access_token,
    decode_access_token,
    hash_password,
    new_session_id,
    verify_password,
)
from app.schemas.auth import AuthTokenResponse, SignInRequest, SignUpRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignUpRequest, request: Request) -> UserResponse:
    users_collection = request.app.state.db["users"]

    existing_user = await users_collection.find_one({"email": payload.email.lower()})
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    now = datetime.now(timezone.utc)
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    permanent_address = payload.permanent_address.strip()
    user_data = {
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "first_name": first_name,
        "last_name": last_name,
        "permanent_address": permanent_address,
        "created_at": now,
        "updated_at": now,
    }
    insert_result = await users_collection.insert_one(user_data)
    user_id = str(insert_result.inserted_id)
    return UserResponse(
        id=user_id,
        email=payload.email.lower(),
        first_name=first_name,
        last_name=last_name,
        permanent_address=permanent_address,
    )


@router.post("/signin", response_model=AuthTokenResponse)
async def signin(payload: SignInRequest, request: Request) -> AuthTokenResponse:
    settings = request.app.state.settings
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
    expires_at = build_session_expiry(session_timeout_minutes=settings.session_timeout_minutes)
    await sessions_collection.insert_one(
        {
            "session_id": session_id,
            "user_id": str(user["_id"]),
            "created_at": now,
            "last_activity_at": now,
            "expires_at": expires_at,
        }
    )

    token = create_access_token(
        user_id=str(user["_id"]),
        session_id=session_id,
        expires_at=expires_at,
        secret_key=request.app.state.jwt_signing_secret,
        algorithm=request.app.state.jwt_algorithm,
    )
    return AuthTokenResponse(
        access_token=token,
        expires_in_seconds=settings.session_timeout_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=str(current_user["_id"]) if isinstance(current_user.get("_id"), ObjectId) else current_user["id"],
        email=current_user["email"],
        first_name=current_user.get("first_name", ""),
        last_name=current_user.get("last_name", ""),
        permanent_address=current_user.get("permanent_address", ""),
    )


@router.post("/logout")
async def logout(
    request: Request,
    token: str = Query(..., min_length=20, max_length=5000),
):
    try:
        payload = decode_access_token(
            token,
            secret_key=request.app.state.jwt_signing_secret,
            algorithm=request.app.state.jwt_algorithm,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    delete_result = await request.app.state.db["sessions"].delete_one(
        {"session_id": session_id, "user_id": user_id}
    )
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return {"status": "ok", "message": "Logged out successfully"}
