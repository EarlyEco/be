from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId


def _avg_numeric(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def evaluate_health_payload(payload: dict[str, Any]) -> dict[str, Any]:
    # Lightweight "LLM-style" structured evaluator fallback.
    # You can replace this implementation with an actual model call later.
    risk_score = 0

    temp = float(payload.get("body_temperature_c") or 36.8)
    if temp >= 39:
        risk_score += 45
    elif temp >= 38:
        risk_score += 30
    elif temp >= 37.5:
        risk_score += 15

    symptoms = payload.get("symptoms") or []
    risk_score += min(len(symptoms) * 4, 20)

    symptom_severities = payload.get("symptom_severities") or {}
    severity_values = [float(v) for v in symptom_severities.values() if isinstance(v, (int, float))]
    risk_score += int(min(_avg_numeric(severity_values) * 2.5, 20))

    vitals = payload.get("vitals") or {}
    spo2 = vitals.get("spo2_percent")
    if isinstance(spo2, (int, float)):
        if spo2 < 92:
            risk_score += 30
        elif spo2 < 95:
            risk_score += 15

    hr = vitals.get("heart_rate_bpm")
    if isinstance(hr, (int, float)) and (hr > 120 or hr < 45):
        risk_score += 10

    feeling_score = payload.get("feeling_score")
    if isinstance(feeling_score, int):
        risk_score += max(0, (5 - feeling_score) * 4)

    testing = payload.get("testing") or {}
    if testing.get("tested_positive_recently") is True:
        risk_score += 35

    exposure = payload.get("exposure") or {}
    if exposure.get("crowded_environment") is True:
        risk_score += 6
    if exposure.get("recent_travel") is True:
        risk_score += 6

    risk_score = max(0, min(int(risk_score), 100))

    if risk_score >= 70:
        risk_level = "high"
        summary = "Elevated indicators detected. Seek medical guidance and reduce exposure."
    elif risk_score >= 40:
        risk_level = "moderate"
        summary = "Some concerning indicators detected. Monitor symptoms and take precautions."
    else:
        risk_level = "low"
        summary = "No strong risk indicators detected at this time."

    is_healthy = risk_score < 40
    return {
        "assessment_status": "completed",
        "is_healthy": is_healthy,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "assessment_summary": summary,
        "assessed_at": datetime.now(timezone.utc),
    }


async def assess_and_store_checkin(db, checkin_id: ObjectId) -> None:
    document = await db["health_checkins"].find_one({"_id": checkin_id})
    if not document:
        return
    assessment = evaluate_health_payload(document)
    await db["health_checkins"].update_one(
        {"_id": checkin_id},
        {"$set": assessment},
    )
