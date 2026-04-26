from pydantic import BaseModel


class CommunityRiskBreakdown(BaseModel):
    low: int
    moderate: int
    high: int


class CommunityWarning(BaseModel):
    severity: str
    title: str
    detail: str


class CommunityHealthResponse(BaseModel):
    location_mode: str
    location_label: str
    lookback_hours: int
    total_reports: int
    unhealthy_reports: int
    unhealthy_ratio: float
    average_risk_score: float | None
    risk_breakdown: CommunityRiskBreakdown
    top_symptoms: list[str]
    warning_level: str
    warnings: list[CommunityWarning]
