from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import math
import re

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.community_hotspots import cluster_docs_to_hotspots, hotspots_to_geojson
from app.schemas.community_health import (
    CommunityHealthResponse,
    CommunityRiskBreakdown,
    CommunityWarning,
)
from app.schemas.community_map import CommunityMapPointsResponse

router = APIRouter(prefix="/community-health", tags=["community-health"])


def _effective_city(city: str | None) -> str | None:
    """Treat UI placeholder strings as 'no city filter' (global community view)."""
    if not city or not str(city).strip():
        return None
    normalized = str(city).strip().lower().replace("+", " ")
    if normalized in {"current location", "my location", "unknown", "here", "all"}:
        return None
    return str(city).strip()


def _warning_level_from_ratio(unhealthy_ratio: float, avg_risk_score: float | None) -> str:
    if unhealthy_ratio >= 0.45 or (avg_risk_score is not None and avg_risk_score >= 70):
        return "critical"
    if unhealthy_ratio >= 0.25 or (avg_risk_score is not None and avg_risk_score >= 45):
        return "warning"
    return "info"


async def _fetch_community_docs(
    db,
    *,
    city: str | None,
    latitude: float | None,
    longitude: float | None,
    radius_km: float,
    lookback_hours: int,
) -> tuple[list[dict], str, str, bool, bool]:
    """Returns (docs, location_mode, location_label, used_full_history_fallback, used_address_fallback)."""
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

    docs = await db["health_checkins"].find(query).sort("recorded_at", -1).limit(5000).to_list(5000)
    used_full_history_fallback = False
    used_address_fallback = False

    if not docs and city:
        city_regex = {"$regex": re.escape(city.strip()), "$options": "i"}
        matching_users = await db["users"].find(
            {"permanent_address": city_regex},
            {"_id": 1},
        ).to_list(100000)
        user_ids = [str(u["_id"]) for u in matching_users]
        if user_ids:
            address_query = {"user_id": {"$in": user_ids}, "recorded_at": {"$gte": since}}
            docs = (
                await db["health_checkins"]
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
            await db["health_checkins"]
            .find(fallback_query)
            .sort("recorded_at", -1)
            .limit(5000)
            .to_list(5000)
        )
        used_full_history_fallback = bool(docs)

    return docs, location_mode, location_label, used_full_history_fallback, used_address_fallback


def _pin_arrays(pins: list[dict]) -> dict:
    """Same pin list under every key the UI may merge."""
    return {
        "hotspots": pins,
        "risk_hotspots": pins,
        "location_hotspots": pins,
        "map_hotspots": pins,
        "anonymized_locations": pins,
        "anonymous_locations": pins,
        "report_locations": pins,
        "location_clusters": pins,
        "clusters": pins,
        "peer_locations": pins,
        "check_in_locations": pins,
        "map_points": pins,
        "recent_location_pins": pins,
    }


@router.get("/overview", response_model=CommunityHealthResponse)
async def get_community_health_overview(
    request: Request,
    city: str | None = Query(default=None),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=5.0, ge=0.1, le=200),
    lookback_hours: int = Query(default=24, ge=1, le=720),
) -> CommunityHealthResponse:
    city = _effective_city(city)
    db = request.app.state.db
    docs, location_mode, location_label, used_full_history_fallback, used_address_fallback = (
        await _fetch_community_docs(
            db,
            city=city,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            lookback_hours=lookback_hours,
        )
    )

    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No community health records found for selected location/time.",
        )

    registered_users_count = await db["users"].count_documents({})

    total = len(docs)
    user_ids_in_sample = {str(d["user_id"]) for d in docs if d.get("user_id") is not None}
    unique_users = len(user_ids_in_sample)

    healthy = sum(1 for d in docs if d.get("is_healthy") is True)
    unhealthy = sum(1 for d in docs if d.get("is_healthy") is False)
    pending = total - healthy - unhealthy
    assessed = healthy + unhealthy
    unhealthy_ratio = (unhealthy / assessed) if assessed else 0.0

    numeric_scores = [int(d["risk_score"]) for d in docs if isinstance(d.get("risk_score"), int)]
    avg_risk = round(sum(numeric_scores) / len(numeric_scores), 2) if numeric_scores else None

    low = sum(1 for d in docs if d.get("risk_level") == "low")
    moderate = sum(1 for d in docs if d.get("risk_level") == "moderate")
    high = sum(1 for d in docs if d.get("risk_level") == "high")
    unknown_risk = total - low - moderate - high

    symptom_counter: Counter[str] = Counter()
    for doc in docs:
        symptom_counter.update(str(s).lower() for s in (doc.get("symptoms") or []) if s)
    top_symptoms = [s for s, _ in symptom_counter.most_common(5)]

    warning_level = _warning_level_from_ratio(unhealthy_ratio, avg_risk)
    warnings: list[CommunityWarning] = []
    if pending > 0:
        warnings.append(
            CommunityWarning(
                severity="info",
                title="Some check-ins are still pending assessment",
                detail=f"{pending} of {total} reports do not have a completed health assessment yet.",
            )
        )
    if warning_level != "info":
        warnings.append(
            CommunityWarning(
                severity=warning_level,
                title="Elevated community health risk",
                detail=(
                    f"{unhealthy} of {assessed or total} assessed reports are unhealthy "
                    f"({round(unhealthy_ratio * 100, 1)}% among assessed)."
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

    pins = cluster_docs_to_hotspots(docs)
    gj = hotspots_to_geojson(pins) if pins else {"type": "FeatureCollection", "features": []}
    pin_kw = _pin_arrays(pins)

    return CommunityHealthResponse(
        location_mode=location_mode,
        location_label=location_label,
        lookback_hours=lookback_hours,
        total_reports=total,
        unique_users=unique_users,
        registered_users_count=registered_users_count,
        healthy_reports=healthy,
        unhealthy_reports=unhealthy,
        pending_reports=pending,
        unhealthy_ratio=round(unhealthy_ratio, 4),
        average_risk_score=avg_risk,
        risk_breakdown=CommunityRiskBreakdown(
            low=low, moderate=moderate, high=high, unknown=max(0, unknown_risk)
        ),
        top_symptoms=top_symptoms,
        warning_level=warning_level,
        warnings=warnings,
        geojson=gj,
        geo_json=gj,
        **pin_kw,
    )


@router.get("/map-points", response_model=CommunityMapPointsResponse)
async def get_community_map_points(
    request: Request,
    city: str | None = Query(default=None),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=5.0, ge=0.1, le=200),
    lookback_hours: int = Query(default=24, ge=1, le=720),
) -> CommunityMapPointsResponse:
    city = _effective_city(city)
    db = request.app.state.db
    docs, _, _, _, _ = await _fetch_community_docs(
        db,
        city=city,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        lookback_hours=lookback_hours,
    )
    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No community health records found for selected location/time.",
        )
    pins = cluster_docs_to_hotspots(docs)
    return CommunityMapPointsResponse(points=pins, hotspots=pins, locations=pins)
