from datetime import datetime, timedelta, timezone
import random

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.health_assessment import evaluate_health_payload
from app.schemas.mock_data import MockDataGenerateResponse

router = APIRouter(prefix="/mock-data", tags=["mock-data"])


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_mock_doc(
    *,
    user_id: str,
    point_time: datetime,
    rng: random.Random,
    idx: int,
) -> dict:
    phase = (idx % 24) / 24.0
    base_temp = 36.6 + (0.15 if 0.2 <= phase <= 0.7 else -0.05)
    temp = round(base_temp + rng.uniform(-0.35, 0.6), 2)

    feeling = max(1, min(5, int(round(4 - (temp - 36.6) * 2 + rng.uniform(-1, 1)))))
    symptoms_pool = ["cough", "fatigue", "headache", "sore_throat", "congestion", "body_aches"]
    symptoms = [s for s in symptoms_pool if rng.random() < 0.18 + max(0, (temp - 37.2) * 0.22)]

    spo2 = round(max(88.0, min(100.0, 98.0 - max(0, temp - 37.5) * 3 + rng.uniform(-1.5, 1.0))), 1)
    hr = int(max(45, min(130, 70 + max(0, temp - 37.2) * 20 + rng.uniform(-10, 14))))

    doc = {
        "user_id": user_id,
        "latitude": round(33.45 + rng.uniform(-0.08, 0.08), 6),
        "longitude": round(-112.07 + rng.uniform(-0.08, 0.08), 6),
        "city": "Phoenix",
        "region": "Arizona",
        "country": "USA",
        "neighborhood": rng.choice(["Downtown", "Tempe", "Mesa", "Scottsdale", "Glendale"]),
        "location_accuracy_m": round(rng.uniform(5, 80), 2),
        "location_source": "mock-generator",
        "body_temperature_c": temp,
        "feeling_score": feeling,
        "symptoms": symptoms,
        "symptom_severities": {
            "cough": 0 if "cough" not in symptoms else rng.randint(2, 8),
            "sore_throat": 0 if "sore_throat" not in symptoms else rng.randint(2, 8),
            "headache": 0 if "headache" not in symptoms else rng.randint(2, 8),
            "body_aches": 0 if "body_aches" not in symptoms else rng.randint(2, 8),
            "fatigue": 0 if "fatigue" not in symptoms else rng.randint(2, 8),
            "nausea": rng.randint(0, 3),
            "congestion": 0 if "congestion" not in symptoms else rng.randint(2, 8),
            "shortness_of_breath": rng.randint(0, 4),
        },
        "vitals": {
            "heart_rate_bpm": hr,
            "spo2_percent": spo2,
            "respiratory_rate_bpm": round(rng.uniform(11, 22), 1),
            "blood_pressure_systolic": int(rng.uniform(100, 138)),
            "blood_pressure_diastolic": int(rng.uniform(62, 90)),
        },
        "wellness": {
            "sleep_hours": round(rng.uniform(5.0, 8.5), 1),
            "sleep_quality_score": rng.randint(2, 5),
            "hydration_level_score": rng.randint(2, 5),
            "stress_level_score": rng.randint(1, 5),
        },
        "exposure": {
            "indoor_or_outdoor": rng.choice(["indoor", "outdoor", "mixed"]),
            "mask_worn": rng.random() < 0.3,
            "crowded_environment": rng.random() < 0.25,
            "recent_travel": rng.random() < 0.08,
            "travel_notes": None,
            "animal_contact": rng.random() < 0.15,
            "animal_contact_notes": None,
        },
        "testing": {
            "tested_positive_recently": rng.random() < 0.03,
            "test_type": "rapid-antigen",
            "test_result": "negative",
        },
        "medications_taken": [],
        "recent_medications_notes": None,
        "chronic_conditions": [],
        "special_notices": None,
        "recorded_at": point_time,
        "created_at": datetime.now(timezone.utc),
    }

    assessment = evaluate_health_payload(doc)
    doc.update(assessment)
    return doc


@router.post("/users/health-checkins/generate", response_model=MockDataGenerateResponse)
async def generate_user_mock_data(
    request: Request,
    email: str = Query("user@example.com", description="User email to generate data for"),
    start_date: datetime = Query(
        datetime(2026, 4, 25, 1, 55, 8, tzinfo=timezone.utc),
        description="Range start datetime (ISO-8601)",
    ),
    end_date: datetime = Query(
        datetime(2026, 4, 26, 1, 55, 8, tzinfo=timezone.utc),
        description="Range end datetime (ISO-8601)",
    ),
    frequency: int = Query(15, ge=1, le=1440, description="Interval in minutes between records"),
) -> MockDataGenerateResponse:
    normalized_email = email.strip().lower()
    start = _as_utc_aware(start_date)
    end = _as_utc_aware(end_date)
    if end <= start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date must be after start_date")

    users_collection = request.app.state.db["users"]
    user = await users_collection.find_one({"email": normalized_email})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found for given email")

    step = timedelta(minutes=frequency)
    total = int((end - start) / step) + 1
    if total > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested range and frequency produce too many records; reduce range or increase interval.",
        )

    user_id = str(user["_id"])
    rng = random.Random(f"{normalized_email}::{start.isoformat()}::{end.isoformat()}::{frequency}")

    docs: list[dict] = []
    current = start
    idx = 0
    while current <= end:
        docs.append(_build_mock_doc(user_id=user_id, point_time=current, rng=rng, idx=idx))
        idx += 1
        current = current + step

    if docs:
        await request.app.state.db["health_checkins"].insert_many(docs)

    return MockDataGenerateResponse(
        email=normalized_email,
        user_id=user_id,
        generated_records=len(docs),
        start_date=start,
        end_date=end,
        frequency=frequency,
    )
