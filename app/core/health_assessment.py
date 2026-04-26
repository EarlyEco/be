from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from typing import Any
from urllib import error, request

from bson import ObjectId


def _avg_numeric(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def evaluate_health_payload(payload: dict[str, Any]) -> dict[str, Any]:
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
    classification = {
        "infection_likelihood": "high" if risk_score >= 70 else "medium" if risk_score >= 40 else "low",
        "respiratory_risk": "high" if (payload.get("vitals") or {}).get("spo2_percent", 100) < 92 else "low",
        "exposure_risk": "high"
        if ((payload.get("exposure") or {}).get("crowded_environment") or (payload.get("exposure") or {}).get("recent_travel"))
        else "low",
        "severity_band": "critical" if risk_score >= 85 else "elevated" if risk_score >= 55 else "baseline",
        "confidence": 0.68,
        "flags": [
            f
            for f in [
                "very_low_oxygen" if ((payload.get("vitals") or {}).get("spo2_percent") or 100) < 92 else None,
                "high_fever" if temp >= 38.5 else None,
                "recent_positive_test" if (payload.get("testing") or {}).get("tested_positive_recently") is True else None,
            ]
            if f
        ],
    }
    return {
        "assessment_status": "completed",
        "is_healthy": is_healthy,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "assessment_summary": summary,
        "assessed_at": datetime.now(timezone.utc),
        "classification": classification,
        "assessment_model": "heuristic-fallback-v1",
    }


def _extract_json_block(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _call_llm_assessment_sync(payload: dict[str, Any], llm_api_key: str) -> dict[str, Any] | None:
    prompt = (
        "You are a health triage classifier. Return strict JSON only with keys: "
        "risk_score (0-100 int), risk_level (low|moderate|high), is_healthy (bool), "
        "assessment_summary (short string), classification (object with infection_likelihood, "
        "respiratory_risk, exposure_risk, severity_band, confidence(0..1), flags(string array)). "
        "Input:\n"
        f"{json.dumps(payload, default=str)}"
    )
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {llm_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=12) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    parsed = _extract_json_block(content)
    if not isinstance(parsed, dict):
        return None
    if "risk_score" not in parsed or "risk_level" not in parsed or "is_healthy" not in parsed:
        return None
    return {
        "assessment_status": "completed",
        "is_healthy": bool(parsed.get("is_healthy")),
        "risk_score": max(0, min(int(parsed.get("risk_score", 0)), 100)),
        "risk_level": str(parsed.get("risk_level") or "moderate"),
        "assessment_summary": str(parsed.get("assessment_summary") or "LLM assessment generated"),
        "assessed_at": datetime.now(timezone.utc),
        "classification": parsed.get("classification") if isinstance(parsed.get("classification"), dict) else None,
        "assessment_model": "gpt-4o-mini",
    }


async def assess_and_store_checkin(db, checkin_id: ObjectId, llm_api_key: str | None = None) -> None:
    document = await db["health_checkins"].find_one({"_id": checkin_id})
    if not document:
        return
    assessment = None
    if llm_api_key:
        assessment = await asyncio.to_thread(_call_llm_assessment_sync, document, llm_api_key)
    if not assessment:
        assessment = evaluate_health_payload(document)
    await db["health_checkins"].update_one(
        {"_id": checkin_id},
        {"$set": assessment},
    )
