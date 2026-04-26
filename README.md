# EarlyEco Backend (`be`)

FastAPI backend for participatory health surveillance and risk intelligence.

This service supports:
- User auth and session management
- Frequent user health check-ins (manual now, auto-ready later)
- Per-user risk classification and trends
- Health suggestions with warnings and future outlook
- Community-level health metrics by location
- Mock data generation and scheduled auto-population jobs

## Tech Stack

- Python + FastAPI
- MongoDB Atlas (Motor async client)
- JWT auth with session records
- Optional LLM-assisted classification (`LLM_API_KEY`)

## Project Structure

- `app/main.py` - app bootstrap, lifespan, middleware, background jobs
- `app/api/v1/endpoints/` - API route sections (`auth`, `user_health`, `community_health`, `suggestions`, `mock_data`, `health`)
- `app/core/` - config, DB setup, security, assessment logic, auto-population loop
- `app/schemas/` - Pydantic request/response models
- `api/index.py` - Vercel entrypoint

## Local Setup

1) Create and activate a virtual environment.

2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Prepare environment file:

```bash
cp environment.example.env environment.env
```

4) Update `environment.env` with real values:

- `MONGODB_URI`
- `MONGODB_DB_NAME`
- optional: `JWT_ALGORITHM`
- optional: `LLM_API_KEY` (for LLM-based assessment path)

5) Run API:

```bash
uvicorn app.main:app --reload
```

6) Open docs:
- Swagger UI: `http://localhost:8080/docs`
- OpenAPI JSON: `http://localhost:8080/openapi.json`

## Authentication Flow

1) `POST /api/v1/auth/signup`  
Create account (no token issued).

2) `POST /api/v1/auth/signin`  
Returns Bearer token and starts session.

3) Use token in protected calls:

`Authorization: Bearer <access_token>`

4) `POST /api/v1/auth/logout?token=<access_token>`  
Closes session tied to that token.

## API Sections

### Health
- `GET /api/v1/health`
- `GET /api/v1/health/db`

### Auth
- `POST /api/v1/auth/signup`
- `POST /api/v1/auth/signin`
- `POST /api/v1/auth/logout` (token in query param)
- `GET /api/v1/auth/me`

### User Health
- `POST /api/v1/users/self/health-checkins`
- `GET /api/v1/users/self/health-checkins/latest`
- `GET /api/v1/users/self/health-checkins`
- `GET /api/v1/users/self/health-checkins/{checkin_id}`
- `GET /api/v1/users/self/health-checkins/trend`

Check-ins store rich health context (location, vitals, symptom severity, exposure, wellness, testing, medications, chronic conditions) plus classification output:
- `is_healthy`
- `risk_score`, `risk_level`
- `classification` (granular dimensions)
- `assessment_summary`, `assessed_at`, `assessment_model`

### Suggestions
- `GET /api/v1/users/self/health-suggestions`

Returns:
- Multi-horizon predictions (6h/24h/72h)
- Likely condition patterns with probabilities
- Risk drivers
- Severity-classified warnings (`info`, `warning`, `critical`)
- Actionable precautions

### Community Health
- `GET /api/v1/community-health/overview`

Supports:
- Generic/global metrics (no location params)
- City-based metrics (`city=...`, partial match supported)
- Radius-based metrics (`latitude`, `longitude`, `radius_km`)
- Lookback filtering (`lookback_hours`)

Returns only aggregated community metrics (no individual records).

### Mock Data
- `POST /api/v1/mock-data/users/health-checkins/generate`

Query params:
- `email`
- `start_date`
- `end_date`
- `frequency`

Generates and stores synthetic check-ins in the selected interval/range.

## Background Auto-Population Job

The app runs an internal scheduler loop (Celery-like behavior) every 15 minutes:
- iterates all users
- generates one new mock check-in per user
- preserves latest known user location
- mocks other health fields
- runs and stores risk assessment/classification

## MongoDB Notes

The app creates indexes for:
- users/sessions auth flows
- health check-in trend and community queries
- secret storage metadata

To clear data without dropping collections/indexes (mongosh):

```javascript
use EarlyEco
db.getCollectionNames().forEach((c) => db.getCollection(c).deleteMany({}))
```

## Vercel Deployment

Configured for Vercel Python runtime via `vercel.json`.

### Required Vercel env vars
- `MONGODB_URI`
- `MONGODB_DB_NAME`

### Optional
- `DEBUG` (default `false`)
- `LLM_API_KEY`

`environment.env` is local only; Vercel does not read your local file.

## Known Behavior

- If required DB config is missing, API routes return a clear misconfiguration response.
- Community endpoint falls back intelligently (city field match, address match, history fallback) before returning no-data.

## License / Usage

Internal hackathon prototype backend for EarlyEco use-case.
