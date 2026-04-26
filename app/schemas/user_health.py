from datetime import datetime

from pydantic import BaseModel, Field, conlist


class HealthCheckInVitals(BaseModel):
    heart_rate_bpm: int | None = Field(default=None, ge=30, le=220)
    spo2_percent: float | None = Field(default=None, ge=70, le=100)
    respiratory_rate_bpm: float | None = Field(default=None, ge=5, le=60)
    blood_pressure_systolic: int | None = Field(default=None, ge=60, le=250)
    blood_pressure_diastolic: int | None = Field(default=None, ge=30, le=200)


class HealthCheckInSymptomSeverities(BaseModel):
    cough: int | None = Field(default=None, ge=0, le=10)
    sore_throat: int | None = Field(default=None, ge=0, le=10)
    headache: int | None = Field(default=None, ge=0, le=10)
    body_aches: int | None = Field(default=None, ge=0, le=10)
    fatigue: int | None = Field(default=None, ge=0, le=10)
    nausea: int | None = Field(default=None, ge=0, le=10)
    congestion: int | None = Field(default=None, ge=0, le=10)
    shortness_of_breath: int | None = Field(default=None, ge=0, le=10)


class HealthCheckInWellness(BaseModel):
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    sleep_quality_score: int | None = Field(default=None, ge=1, le=5)
    hydration_level_score: int | None = Field(default=None, ge=1, le=5)
    stress_level_score: int | None = Field(default=None, ge=1, le=5)


class HealthCheckInExposure(BaseModel):
    indoor_or_outdoor: str | None = Field(default=None, max_length=20)
    mask_worn: bool | None = None
    crowded_environment: bool | None = None
    recent_travel: bool | None = None
    travel_notes: str | None = Field(default=None, max_length=500)
    animal_contact: bool | None = None
    animal_contact_notes: str | None = Field(default=None, max_length=500)


class HealthCheckInTesting(BaseModel):
    tested_positive_recently: bool | None = None
    test_type: str | None = Field(default=None, max_length=80)
    test_result: str | None = Field(default=None, max_length=40)


class HealthCheckInCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    city: str = Field(min_length=2, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    neighborhood: str | None = Field(default=None, max_length=120)
    location_accuracy_m: float | None = Field(default=None, ge=0, le=50000)
    location_source: str | None = Field(default=None, max_length=40)

    body_temperature_c: float = Field(ge=30, le=45, description="Body temperature in Celsius")
    feeling_score: int | None = Field(default=None, ge=1, le=5)
    symptoms: conlist(str, max_length=25) = Field(default_factory=list)
    symptom_severities: HealthCheckInSymptomSeverities | None = None
    vitals: HealthCheckInVitals | None = None
    wellness: HealthCheckInWellness | None = None
    exposure: HealthCheckInExposure | None = None
    testing: HealthCheckInTesting | None = None

    medications_taken: conlist(str, max_length=20) = Field(default_factory=list)
    recent_medications_notes: str | None = Field(default=None, max_length=1000)
    chronic_conditions: conlist(str, max_length=15) = Field(default_factory=list)

    special_notices: str | None = Field(default=None, max_length=2000)

    recorded_at: datetime | None = Field(
        default=None,
        description="Optional client-provided timestamp; defaults to server time if omitted",
    )


class HealthCheckInResponse(BaseModel):
    id: str
    user_id: str
    latitude: float
    longitude: float
    city: str
    region: str | None
    country: str | None
    neighborhood: str | None
    location_accuracy_m: float | None
    location_source: str | None
    body_temperature_c: float
    feeling_score: int | None
    symptoms: list[str]
    symptom_severities: HealthCheckInSymptomSeverities | None
    vitals: HealthCheckInVitals | None
    wellness: HealthCheckInWellness | None
    exposure: HealthCheckInExposure | None
    testing: HealthCheckInTesting | None
    medications_taken: list[str]
    recent_medications_notes: str | None
    chronic_conditions: list[str]
    special_notices: str | None
    recorded_at: datetime
    assessment_status: str
    is_healthy: bool | None
    risk_score: int | None
    risk_level: str | None
    assessment_summary: str | None
    assessed_at: datetime | None
    classification: dict | None
    assessment_model: str | None


class HealthTrendResponse(BaseModel):
    total_points: int
    healthy_points: int
    unhealthy_points: int
    low_risk_points: int
    moderate_risk_points: int
    high_risk_points: int
    avg_risk_score: float | None
    latest_is_healthy: bool | None
    latest_risk_score: int | None
    trend_direction: str
