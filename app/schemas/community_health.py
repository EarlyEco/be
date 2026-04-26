from typing import Any

from pydantic import BaseModel, Field


class CommunityRiskBreakdown(BaseModel):
    low: int
    moderate: int
    high: int
    unknown: int = 0


class CommunityWarning(BaseModel):
    severity: str
    title: str
    detail: str


class CommunityHealthResponse(BaseModel):
    location_mode: str
    location_label: str
    lookback_hours: int
    total_reports: int
    unique_users: int
    registered_users_count: int
    healthy_reports: int
    unhealthy_reports: int
    pending_reports: int
    unhealthy_ratio: float
    average_risk_score: float | None
    risk_breakdown: CommunityRiskBreakdown
    top_symptoms: list[str]
    warning_level: str
    warnings: list[CommunityWarning]
    # Map pins (grid-clustered, approximate centers). UI may merge any non-empty array below.
    hotspots: list[dict[str, Any]] = Field(default_factory=list)
    risk_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    location_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    map_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    anonymized_locations: list[dict[str, Any]] = Field(default_factory=list)
    anonymous_locations: list[dict[str, Any]] = Field(default_factory=list)
    report_locations: list[dict[str, Any]] = Field(default_factory=list)
    location_clusters: list[dict[str, Any]] = Field(default_factory=list)
    clusters: list[dict[str, Any]] = Field(default_factory=list)
    peer_locations: list[dict[str, Any]] = Field(default_factory=list)
    check_in_locations: list[dict[str, Any]] = Field(default_factory=list)
    map_points: list[dict[str, Any]] = Field(default_factory=list)
    recent_location_pins: list[dict[str, Any]] = Field(default_factory=list)
    geojson: dict[str, Any] | None = None
    geo_json: dict[str, Any] | None = None
