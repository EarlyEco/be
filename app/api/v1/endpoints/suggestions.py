from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies.auth import get_current_user
from app.schemas.suggestions import (
    ConditionProbability,
    HealthPrediction,
    HealthSuggestion,
    HealthSuggestionsResponse,
    HealthWarning,
)

router = APIRouter(prefix="/users/self", tags=["suggestions"])


def _classify_outlook(latest_risk_score: int | None, avg_risk_score: float | None) -> str:
    if latest_risk_score is None:
        return "insufficient_data"
    if latest_risk_score >= 75:
        return "high_risk_next_24h"
    if latest_risk_score >= 45:
        return "moderate_risk_monitor_closely"
    if avg_risk_score is not None and avg_risk_score > latest_risk_score + 8:
        return "improving_but_continue_monitoring"
    return "stable_low_risk"


def _severity_from_risk(risk_score: int | None) -> str:
    if risk_score is None:
        return "info"
    if risk_score >= 70:
        return "critical"
    if risk_score >= 40:
        return "warning"
    return "info"


def _risk_to_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "moderate"
    return "low"


def _project_risk(base: int, slope_per_point: float, horizon_hours: int, points_per_hour: float) -> int:
    projected = base + (slope_per_point * points_per_hour * horizon_hours)
    return max(0, min(100, int(round(projected))))


@router.get("/health-suggestions", response_model=HealthSuggestionsResponse)
async def get_health_suggestions(
    request: Request,
    current_user=Depends(get_current_user),
    lookback_hours: int = Query(default=48, ge=1, le=720),
) -> HealthSuggestionsResponse:
    user_id = str(current_user["_id"])
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    cursor = (
        request.app.state.db["health_checkins"]
        .find({"user_id": user_id, "recorded_at": {"$gte": since}})
        .sort("recorded_at", -1)
        .limit(200)
    )
    docs = [doc async for doc in cursor]
    if not docs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No health check-ins found")

    latest = docs[0]
    latest_risk_score = latest.get("risk_score")
    latest_risk_level = latest.get("risk_level")
    is_healthy = latest.get("is_healthy")

    numeric_scores = [int(d["risk_score"]) for d in docs if isinstance(d.get("risk_score"), int)]
    avg_risk_score = (sum(numeric_scores) / len(numeric_scores)) if numeric_scores else None
    future_outlook = _classify_outlook(latest_risk_score, avg_risk_score)

    warnings: list[HealthWarning] = []
    suggestions: list[HealthSuggestion] = []
    likely_conditions: list[ConditionProbability] = []
    key_risk_drivers: list[str] = []

    severity = _severity_from_risk(latest_risk_score if isinstance(latest_risk_score, int) else None)
    if severity != "info":
        warnings.append(
            HealthWarning(
                severity=severity,
                title="Elevated health risk detected",
                detail=f"Latest risk score is {latest_risk_score} ({latest_risk_level}).",
            )
        )

    latest_temp = latest.get("body_temperature_c")
    if isinstance(latest_temp, (int, float)) and latest_temp >= 38:
        key_risk_drivers.append("high_body_temperature")
        warnings.append(
            HealthWarning(
                severity="warning" if latest_temp < 39 else "critical",
                title="High temperature trend",
                detail=f"Current temperature is {latest_temp} C.",
            )
        )
        suggestions.append(
            HealthSuggestion(
                category="fever_management",
                action="Hydrate, rest, and re-check temperature every 2-4 hours.",
                precaution="Seek urgent care if fever remains very high or worsens.",
            )
        )

    latest_vitals = latest.get("vitals") or {}
    spo2 = latest_vitals.get("spo2_percent")
    if isinstance(spo2, (int, float)) and spo2 < 94:
        key_risk_drivers.append("low_oxygen_saturation")
        warnings.append(
            HealthWarning(
                severity="critical" if spo2 < 92 else "warning",
                title="Low oxygen saturation",
                detail=f"Latest SpO2 is {spo2}%.",
            )
        )
        suggestions.append(
            HealthSuggestion(
                category="respiratory_care",
                action="Limit exertion and monitor oxygen closely.",
                precaution="Contact a clinician immediately if SpO2 continues to drop.",
            )
        )

    symptoms = [str(s).lower() for s in (latest.get("symptoms") or [])]
    if symptoms:
        key_risk_drivers.append("active_symptoms")
        suggestions.append(
            HealthSuggestion(
                category="symptom_tracking",
                action="Continue logging symptoms every few hours for better trend visibility.",
                precaution="If symptoms escalate rapidly, seek professional evaluation.",
            )
        )

    exposure = latest.get("exposure") or {}
    if exposure.get("crowded_environment") is True or exposure.get("recent_travel") is True:
        key_risk_drivers.append("recent_high_exposure")
        suggestions.append(
            HealthSuggestion(
                category="exposure_precaution",
                action="Reduce close contact and prefer ventilated spaces for the next 48 hours.",
                precaution="Use mask protection in crowded indoor environments.",
            )
        )

    if not suggestions:
        suggestions.append(
            HealthSuggestion(
                category="maintenance",
                action="Maintain hydration, sleep, and daily check-ins to keep trend confidence high.",
                precaution=None,
            )
        )

    if "low_oxygen_saturation" in key_risk_drivers:
        likely_conditions.append(
            ConditionProbability(
                condition="respiratory_distress_pattern",
                probability=0.78,
                severity="critical",
                rationale="Low SpO2 and elevated symptom load indicate potential respiratory involvement.",
            )
        )
    if "high_body_temperature" in key_risk_drivers:
        likely_conditions.append(
            ConditionProbability(
                condition="acute_febrile_illness_pattern",
                probability=0.72,
                severity="warning",
                rationale="Persistent elevated temperature and symptom severity suggest active febrile condition.",
            )
        )
    if not likely_conditions:
        likely_conditions.append(
            ConditionProbability(
                condition="low_probability_of_acute_infection",
                probability=0.24,
                severity="info",
                rationale="No strong concurrent fever/oxygen warning profile in latest check-ins.",
            )
        )

    # Trend-aware projection: estimate slope across available points.
    predictions: list[HealthPrediction] = []
    if numeric_scores:
        slope = 0.0
        if len(numeric_scores) > 1:
            slope = (numeric_scores[0] - numeric_scores[-1]) / max(1, len(numeric_scores) - 1)
        points_per_hour = max(0.2, len(docs) / max(1.0, lookback_hours))
        base = int(latest_risk_score) if isinstance(latest_risk_score, int) else int(numeric_scores[0])
        for horizon in (6, 24, 72):
            projected = _project_risk(base, slope, horizon, points_per_hour)
            level = _risk_to_level(projected)
            predictions.append(
                HealthPrediction(
                    horizon_hours=horizon,
                    risk_score=projected,
                    risk_level=level,
                    is_healthy_likely=projected < 40,
                    confidence=0.62 if len(numeric_scores) < 8 else 0.75,
                )
            )
    else:
        predictions = [
            HealthPrediction(
                horizon_hours=h,
                risk_score=0,
                risk_level="low",
                is_healthy_likely=True,
                confidence=0.2,
            )
            for h in (6, 24, 72)
        ]

    return HealthSuggestionsResponse(
        user_id=user_id,
        is_healthy=is_healthy,
        latest_risk_score=latest_risk_score if isinstance(latest_risk_score, int) else None,
        latest_risk_level=latest_risk_level if isinstance(latest_risk_level, str) else None,
        future_outlook=future_outlook,
        predictions=predictions,
        likely_conditions=likely_conditions,
        key_risk_drivers=key_risk_drivers,
        warnings=warnings,
        suggestions=suggestions,
        source_points=len(docs),
    )
