from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import math
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies.auth import get_current_user
from app.schemas.community_health import (
    CommunityHealthResponse,
    CommunityRiskBreakdown,
    CommunityWarning,
)

router = APIRouter(prefix="/community-health", tags=["community-health"])


def _warning_level_from_ratio(unhealthy_ratio: float, avg_risk_score: float | None) -> str:
    if unhealthy_ratio >= 0.45 or (avg_risk_score is not None and avg_risk_score >= 70):
        return "critical"
    if unhealthy_ratio >= 0.25 or (avg_risk_score is not None and avg_risk_score >= 45):
        return "warning"
    return "info"


@router.get("/overview", response_model=CommunityHealthResponse)
async def get_community_health_overview(
    request: Request,
    current_user=Depends(get_current_user),
    city: str | None = Query(default=None),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=5.0, ge=0.1, le=200),
    lookback_hours: int = Query(default=24, ge=1, le=720),
) -> CommunityHealthResponse:
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    query: dict = {"recorded_at": {"$gte": since}}
    location_mode = "global"
    location_label = "all-locations"

    if city:
        location_mode = "city"
        city_term = city.strip()
        city_regex = {"$regex": re.escape(city_term), "$options": "i"}
        query["$or"] = [
            {"city": city_regex},
            {"region": city_regex},
            {"country": city_regex},
            {"neighborhood": city_regex},
        ]
        location_label = city_term
    elif latitude is not None and longitude is not None:
        location_mode = "radius"
        location_label = f"{latitude:.4f},{longitude:.4f} ({radius_km}km)"
        lat_delta = radius_km / 111.0
        lon_divisor = max(0.1, 111.0 * abs(math.cos(math.radians(float(latitude)))))
        lon_delta = radius_km / lon_divisor
        query["latitude"] = {"$gte": float(latitude) - lat_delta, "$lte": float(latitude) + lat_delta}
        query["longitude"] = {"$gte": float(longitude) - lon_delta, "$lte": float(longitude) + lon_delta}

    docs = await request.app.state.db["health_checkins"].find(query).sort("recorded_at", -1).limit(5000).to_list(5000)
    used_full_history_fallback = False
    used_address_fallback = False

    # If city-specific check-ins are not tagged with that city, fall back to users
    # whose permanent address matches the city and aggregate their check-ins.
    if not docs and city:
        city_regex = {"$regex": re.escape(city.strip()), "$options": "i"}
        matching_users = await request.app.state.db["users"].find(
            {"permanent_address": city_regex},
            {"_id": 1},
        ).to_list(100000)
        user_ids = [str(u["_id"]) for u in matching_users]
        if user_ids:
            address_query = {"user_id": {"$in": user_ids}, "recorded_at": {"$gte": since}}
            docs = (
                await request.app.state.db["health_checkins"]
                .find(address_query)
                .sort("recorded_at", -1)
                .limit(5000)
                .to_list(5000)
            )
            used_address_fallback = bool(docs)

    if not docs:
        fallback_query = dict(query)
        fallback_query.pop("recorded_at", None)
        docs = (
            await request.app.state.db["health_checkins"]
            .find(fallback_query)
            .sort("recorded_at", -1)
            .limit(5000)
            .to_list(5000)
        )
        used_full_history_fallback = bool(docs)

    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No community health records found for selected location/time.",
        )

    total = len(docs)
    unhealthy = sum(1 for d in docs if d.get("is_healthy") is False)
    unhealthy_ratio = unhealthy / total if total else 0.0
    numeric_scores = [int(d["risk_score"]) for d in docs if isinstance(d.get("risk_score"), int)]
    avg_risk = round(sum(numeric_scores) / len(numeric_scores), 2) if numeric_scores else None

    low = sum(1 for d in docs if d.get("risk_level") == "low")
    moderate = sum(1 for d in docs if d.get("risk_level") == "moderate")
    high = sum(1 for d in docs if d.get("risk_level") == "high")

    symptom_counter: Counter[str] = Counter()
    for doc in docs:
        symptom_counter.update(str(s).lower() for s in (doc.get("symptoms") or []) if s)
    top_symptoms = [s for s, _ in symptom_counter.most_common(5)]

    warning_level = _warning_level_from_ratio(unhealthy_ratio, avg_risk)
    warnings: list[CommunityWarning] = []
    if warning_level != "info":
        warnings.append(
            CommunityWarning(
                severity=warning_level,
                title="Elevated community health risk",
                detail=(
                    f"{unhealthy} of {total} reports are currently unhealthy "
                    f"({round(unhealthy_ratio * 100, 1)}%)."
                ),
            )
        )
    if high > 0:
        warnings.append(
            CommunityWarning(
                severity="critical" if high >= max(3, total * 0.1) else "warning",
                title="High-risk cases present",
                detail=f"{high} high-risk reports detected in selected window.",
            )
        )
    if top_symptoms:
        warnings.append(
            CommunityWarning(
                severity="info",
                title="Most reported symptoms",
                detail=", ".join(top_symptoms),
            )
        )
    if used_full_history_fallback:
        warnings.append(
            CommunityWarning(
                severity="info",
                title="Using historical community data",
                detail=(
                    f"No reports were found in the last {lookback_hours} hour(s), "
                    "so older records from the same location were used."
                ),
            )
        )
    if used_address_fallback:
        warnings.append(
            CommunityWarning(
                severity="info",
                title="Using address-based community match",
                detail=(
                    "No direct city-tagged check-ins found. Aggregation used users whose "
                    "permanent address matches the selected city."
                ),
            )
        )

    return CommunityHealthResponse(
        location_mode=location_mode,
        location_label=location_label,
        lookback_hours=lookback_hours,
        total_reports=total,
        unhealthy_reports=unhealthy,
        unhealthy_ratio=round(unhealthy_ratio, 4),
        average_risk_score=avg_risk,
        risk_breakdown=CommunityRiskBreakdown(low=low, moderate=moderate, high=high),
        top_symptoms=top_symptoms,
        warning_level=warning_level,
        warnings=warnings,
    )
