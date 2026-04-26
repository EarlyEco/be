from pydantic import BaseModel


class HealthWarning(BaseModel):
    severity: str  # info | warning | critical
    title: str
    detail: str


class HealthSuggestion(BaseModel):
    category: str
    action: str
    precaution: str | None = None


class HealthPrediction(BaseModel):
    horizon_hours: int
    risk_score: int
    risk_level: str
    is_healthy_likely: bool
    confidence: float


class ConditionProbability(BaseModel):
    condition: str
    probability: float
    severity: str
    rationale: str


class HealthSuggestionsResponse(BaseModel):
    user_id: str
    is_healthy: bool | None
    latest_risk_score: int | None
    latest_risk_level: str | None
    future_outlook: str
    predictions: list[HealthPrediction]
    likely_conditions: list[ConditionProbability]
    key_risk_drivers: list[str]
    warnings: list[HealthWarning]
    suggestions: list[HealthSuggestion]
    source_points: int
