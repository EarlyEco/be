from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies.auth import get_current_user
from app.schemas.user_health import (
    HealthCheckInCreate,
    HealthCheckInExposure,
    HealthCheckInResponse,
    HealthCheckInSymptomSeverities,
    HealthCheckInTesting,
    HealthCheckInVitals,
    HealthCheckInWellness,
)

router = APIRouter(prefix="/users/self", tags=["user-health"])


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clean_str_list(values: list[str], *, max_items: int | None = None) -> list[str]:
    cleaned = [item.strip() for item in values if item and item.strip()]
    if max_items is not None:
        return cleaned[:max_items]
    return cleaned


def _serialize_checkin(document: dict) -> HealthCheckInResponse:
    recorded_at = document["recorded_at"]
    if isinstance(recorded_at, datetime):
        recorded_at = _as_utc_aware(recorded_at)

    symptom_severities = document.get("symptom_severities")
    if isinstance(symptom_severities, dict):
        symptom_severities = HealthCheckInSymptomSeverities.model_validate(symptom_severities)

    vitals = document.get("vitals")
    if isinstance(vitals, dict):
        vitals = HealthCheckInVitals.model_validate(vitals)

    wellness = document.get("wellness")
    if isinstance(wellness, dict):
        wellness = HealthCheckInWellness.model_validate(wellness)

    exposure = document.get("exposure")
    if isinstance(exposure, dict):
        exposure = HealthCheckInExposure.model_validate(exposure)

    testing = document.get("testing")
    if isinstance(testing, dict):
        testing = HealthCheckInTesting.model_validate(testing)

    return HealthCheckInResponse(
        id=str(document["_id"]),
        user_id=str(document["user_id"]),
        latitude=float(document["latitude"]),
        longitude=float(document["longitude"]),
        city=str(document["city"]),
        region=document.get("region"),
        country=document.get("country"),
        neighborhood=document.get("neighborhood"),
        location_accuracy_m=document.get("location_accuracy_m"),
        location_source=document.get("location_source"),
        body_temperature_c=float(document["body_temperature_c"]),
        feeling_score=document.get("feeling_score"),
        symptoms=list(document.get("symptoms") or []),
        symptom_severities=symptom_severities,
        vitals=vitals,
        wellness=wellness,
        exposure=exposure,
        testing=testing,
        medications_taken=list(document.get("medications_taken") or []),
        recent_medications_notes=document.get("recent_medications_notes"),
        chronic_conditions=list(document.get("chronic_conditions") or []),
        special_notices=document.get("special_notices"),
        recorded_at=recorded_at,
    )


@router.post(
    "/health-checkins",
    response_model=HealthCheckInResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_health_checkin(
    payload: HealthCheckInCreate,
    request: Request,
    current_user=Depends(get_current_user),
) -> HealthCheckInResponse:
    user_id = str(current_user["_id"])
    now = datetime.now(timezone.utc)
    recorded_at = _as_utc_aware(payload.recorded_at) if payload.recorded_at else now

    doc = {
        "user_id": user_id,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "city": payload.city.strip(),
        "region": payload.region.strip() if payload.region else None,
        "country": payload.country.strip() if payload.country else None,
        "neighborhood": payload.neighborhood.strip() if payload.neighborhood else None,
        "location_accuracy_m": payload.location_accuracy_m,
        "location_source": payload.location_source.strip() if payload.location_source else None,
        "body_temperature_c": payload.body_temperature_c,
        "feeling_score": payload.feeling_score,
        "symptoms": _clean_str_list(list(payload.symptoms)),
        "symptom_severities": payload.symptom_severities.model_dump(exclude_none=True)
        if payload.symptom_severities
        else None,
        "vitals": payload.vitals.model_dump(exclude_none=True) if payload.vitals else None,
        "wellness": payload.wellness.model_dump(exclude_none=True) if payload.wellness else None,
        "exposure": payload.exposure.model_dump(exclude_none=True) if payload.exposure else None,
        "testing": payload.testing.model_dump(exclude_none=True) if payload.testing else None,
        "medications_taken": _clean_str_list(list(payload.medications_taken)),
        "recent_medications_notes": payload.recent_medications_notes.strip()
        if payload.recent_medications_notes
        else None,
        "chronic_conditions": _clean_str_list(list(payload.chronic_conditions)),
        "special_notices": payload.special_notices.strip() if payload.special_notices else None,
        "recorded_at": recorded_at,
        "created_at": now,
    }

    insert_result = await request.app.state.db["health_checkins"].insert_one(doc)
    stored = await request.app.state.db["health_checkins"].find_one({"_id": insert_result.inserted_id})
    if not stored:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store check-in")
    return _serialize_checkin(stored)


@router.get("/health-checkins/latest", response_model=HealthCheckInResponse)
async def get_latest_health_checkin(
    request: Request,
    current_user=Depends(get_current_user),
) -> HealthCheckInResponse:
    user_id = str(current_user["_id"])
    document = await request.app.state.db["health_checkins"].find_one(
        {"user_id": user_id},
        sort=[("recorded_at", -1)],
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No check-ins found")
    return _serialize_checkin(document)


@router.get("/health-checkins", response_model=list[HealthCheckInResponse])
async def list_health_checkins(
    request: Request,
    current_user=Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[HealthCheckInResponse]:
    user_id = str(current_user["_id"])
    query: dict = {"user_id": user_id}
    if since:
        query.setdefault("recorded_at", {})["$gte"] = _as_utc_aware(since)
    if until:
        query.setdefault("recorded_at", {})["$lte"] = _as_utc_aware(until)

    cursor = (
        request.app.state.db["health_checkins"]
        .find(query)
        .sort("recorded_at", -1)
        .limit(limit)
    )
    results: list[HealthCheckInResponse] = []
    async for document in cursor:
        results.append(_serialize_checkin(document))
    return results


@router.get("/health-checkins/{checkin_id}", response_model=HealthCheckInResponse)
async def get_health_checkin(
    checkin_id: str,
    request: Request,
    current_user=Depends(get_current_user),
) -> HealthCheckInResponse:
    user_id = str(current_user["_id"])
    try:
        object_id = ObjectId(checkin_id)
    except InvalidId as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid check-in id") from exc

    document = await request.app.state.db["health_checkins"].find_one({"_id": object_id, "user_id": user_id})
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found")
    return _serialize_checkin(document)
