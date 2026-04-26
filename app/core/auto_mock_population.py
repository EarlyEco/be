from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import random

from app.core.health_assessment import assess_and_store_checkin


def _build_auto_mock_doc(*, user_id: str, latest: dict | None, rng: random.Random) -> dict:
    latest = latest or {}
    latest_temp = latest.get("body_temperature_c")
    baseline_temp = float(latest_temp) if isinstance(latest_temp, (int, float)) else 36.7
    temp = round(max(35.5, min(40.5, baseline_temp + rng.uniform(-0.25, 0.45))), 2)

    latest_feeling = latest.get("feeling_score")
    baseline_feeling = int(latest_feeling) if isinstance(latest_feeling, int) else 4
    feeling = max(1, min(5, baseline_feeling + rng.choice([-1, 0, 0, 1])))

    symptoms_pool = ["cough", "fatigue", "headache", "sore_throat", "congestion", "body_aches"]
    symptoms = [s for s in symptoms_pool if rng.random() < (0.12 + max(0, temp - 37.3) * 0.2)]

    doc = {
        "user_id": user_id,
        # Keep latest location stable, as requested
        "latitude": latest.get("latitude", round(33.45 + rng.uniform(-0.02, 0.02), 6)),
        "longitude": latest.get("longitude", round(-112.07 + rng.uniform(-0.02, 0.02), 6)),
        "city": latest.get("city", "Phoenix"),
        "region": latest.get("region", "Arizona"),
        "country": latest.get("country", "USA"),
        "neighborhood": latest.get("neighborhood"),
        "location_accuracy_m": latest.get("location_accuracy_m", round(rng.uniform(8, 40), 2)),
        "location_source": "auto-population",
        "body_temperature_c": temp,
        "feeling_score": feeling,
        "symptoms": symptoms,
        "symptom_severities": {
            "cough": 0 if "cough" not in symptoms else rng.randint(2, 7),
            "sore_throat": 0 if "sore_throat" not in symptoms else rng.randint(2, 7),
            "headache": 0 if "headache" not in symptoms else rng.randint(2, 7),
            "body_aches": 0 if "body_aches" not in symptoms else rng.randint(2, 7),
            "fatigue": 0 if "fatigue" not in symptoms else rng.randint(2, 7),
            "nausea": rng.randint(0, 3),
            "congestion": 0 if "congestion" not in symptoms else rng.randint(2, 7),
            "shortness_of_breath": rng.randint(0, 4),
        },
        "vitals": {
            "heart_rate_bpm": int(max(45, min(130, 72 + (temp - 36.8) * 18 + rng.uniform(-10, 12)))),
            "spo2_percent": round(max(89.0, min(100.0, 98.0 - max(0, temp - 37.5) * 2.5 + rng.uniform(-1.2, 0.8))), 1),
            "respiratory_rate_bpm": round(rng.uniform(11, 22), 1),
            "blood_pressure_systolic": int(rng.uniform(100, 138)),
            "blood_pressure_diastolic": int(rng.uniform(62, 90)),
        },
        "wellness": {
            "sleep_hours": round(rng.uniform(5.5, 8.0), 1),
            "sleep_quality_score": rng.randint(2, 5),
            "hydration_level_score": rng.randint(2, 5),
            "stress_level_score": rng.randint(1, 5),
        },
        "exposure": {
            "indoor_or_outdoor": rng.choice(["indoor", "outdoor", "mixed"]),
            "mask_worn": rng.random() < 0.35,
            "crowded_environment": rng.random() < 0.2,
            "recent_travel": rng.random() < 0.06,
            "travel_notes": None,
            "animal_contact": rng.random() < 0.12,
            "animal_contact_notes": None,
        },
        "testing": {
            "tested_positive_recently": rng.random() < 0.02,
            "test_type": "rapid-antigen",
            "test_result": "negative",
        },
        "medications_taken": [],
        "recent_medications_notes": None,
        "chronic_conditions": latest.get("chronic_conditions", []),
        "special_notices": None,
        "recorded_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "assessment_status": "pending",
        "is_healthy": None,
        "risk_score": None,
        "risk_level": None,
        "assessment_summary": None,
        "assessed_at": None,
        "classification": None,
        "assessment_model": None,
    }
    return doc


async def populate_once_for_all_users(app) -> int:
    db = app.state.db
    users = await db["users"].find({}).to_list(length=100000)
    generated = 0
    for user in users:
        user_id = str(user["_id"])
        latest = await db["health_checkins"].find_one({"user_id": user_id}, sort=[("recorded_at", -1)])
        rng = random.Random(f"{user_id}:{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H-%M')}")
        doc = _build_auto_mock_doc(user_id=user_id, latest=latest, rng=rng)
        insert_result = await db["health_checkins"].insert_one(doc)
        await assess_and_store_checkin(db, insert_result.inserted_id, app.state.settings.llm_api_key)
        generated += 1
    return generated


async def auto_population_loop(app) -> None:
    interval_minutes = 15
    while True:
        try:
            if getattr(app.state, "ready", False) and getattr(app.state, "db", None) is not None:
                await populate_once_for_all_users(app)
        except Exception:
            # Keep loop alive; logging can be added later.
            pass
        await asyncio.sleep(interval_minutes * 60)
