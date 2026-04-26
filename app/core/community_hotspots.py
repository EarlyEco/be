"""Grid-cluster health check-ins for map pins (approximate locations, not exact homes)."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _coords(doc: dict) -> tuple[float, float] | None:
    try:
        lat = float(doc["latitude"])
        lon = float(doc["longitude"])
        if math.isfinite(lat) and math.isfinite(lon) and (-90 <= lat <= 90) and (-180 <= lon <= 180):
            return lat, lon
    except (KeyError, TypeError, ValueError):
        pass
    return None


def _grid_key(lat: float, lon: float) -> tuple[int, int]:
    """~1.1 km latitude bins at mid-latitudes when using 2 decimal places."""
    return (round(lat * 100), round(lon * 100))


def _infer_severity_from_group(group: list[dict]) -> str:
    if any(d.get("risk_level") == "high" for d in group):
        return "critical"
    scores = [int(d["risk_score"]) for d in group if isinstance(d.get("risk_score"), int)]
    mx = max(scores) if scores else 0
    if mx >= 70 or any(d.get("risk_level") == "moderate" for d in group):
        return "warning" if mx < 70 else "critical"
    if mx >= 40:
        return "warning"
    if any(d.get("is_healthy") is False for d in group):
        return "warning"
    return "info"


def _risk_level_for_group(group: list[dict], max_score: int) -> str:
    if any(d.get("risk_level") == "high" for d in group):
        return "high"
    if max_score >= 70:
        return "high"
    if any(d.get("risk_level") == "moderate" for d in group) or max_score >= 40:
        return "moderate"
    return "low"


def cluster_docs_to_hotspots(docs: list[dict]) -> list[dict]:
    buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for doc in docs:
        c = _coords(doc)
        if not c:
            continue
        lat, lon = c
        buckets[_grid_key(lat, lon)].append(doc)

    pins: list[dict] = []
    for (gi, gj), group in buckets.items():
        lats: list[float] = []
        lons: list[float] = []
        for d in group:
            cc = _coords(d)
            if cc:
                lats.append(cc[0])
                lons.append(cc[1])
        if not lats:
            continue
        clat = sum(lats) / len(lats)
        clon = sum(lons) / len(lons)
        scores = [int(d["risk_score"]) for d in group if isinstance(d.get("risk_score"), int)]
        max_score = max(scores) if scores else 0
        avg_risk = round(sum(scores) / len(scores), 2) if scores else None
        count = len(group)
        severity = _infer_severity_from_group(group)
        risk_level = _risk_level_for_group(group, max_score)
        label = f"Grid {gi % 100:02d}-{gj % 100:02d} · {count} report(s)"
        pin_id = f"grid_{gi}_{gj}"
        pin: dict[str, Any] = {
            "id": pin_id,
            "latitude": round(clat, 5),
            "longitude": round(clon, 5),
            "lat": round(clat, 5),
            "lon": round(clon, 5),
            "reports_count": count,
            "count": count,
            "cases": count,
            "label": label,
            "name": label,
            "severity": severity,
            "risk_level": risk_level,
            "average_risk_score": avg_risk,
        }
        pins.append(pin)

    pins.sort(key=lambda p: int(p.get("reports_count") or 0), reverse=True)
    return pins


def hotspots_to_geojson(hotspots: list[dict]) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for h in hotspots:
        lat = h.get("latitude")
        lon = h.get("longitude")
        if lat is None or lon is None:
            continue
        props = {
            k: v
            for k, v in h.items()
            if k not in ("latitude", "longitude", "lat", "lon", "geometry") and v is not None
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}
