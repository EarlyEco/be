# EarlyEco Backend (`be`)

EarlyEco Backend is a FastAPI service for participatory health intelligence, built to collect frequent user health check-ins, assess individual risk, and generate actionable insights at both user and community levels. The system supports authentication, session management, health trend tracking, warning/suggestion generation, community-location risk summaries, and synthetic data generation for demo/testing workflows.

## Replicate Locally

1. Clone and enter project:

```bash
git clone <your-repo-url>
cd be
```

2. Create and activate virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create local environment file:

```bash
cp environment.example.env environment.env
```

5. Update `environment.env` with real values:
- `MONGODB_URI`
- `MONGODB_DB_NAME`
- optional: `JWT_ALGORITHM`
- optional: `LLM_API_KEY`

6. Run server:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

7. Open:
- `http://127.0.0.1:8080/docs`
- `http://127.0.0.1:8080/openapi.json`

## Project Info

### Main Features
- Auth with session-based JWT flow
- User health check-ins (location + symptoms + vitals + wellness)
- Risk classification and trend analysis
- Suggestions with warnings and future outlook
- Community health overview by city or nearby radius
- Mock-data generation and automatic 15-minute population loop

### Stack
- FastAPI
- MongoDB Atlas (Motor/PyMongo)
- JWT auth
- Optional LLM-assisted health assessment

### Important Files
- `app/main.py` - app startup, middleware, background loop
- `app/api/v1/endpoints/` - API sections (`auth`, `user_health`, `community_health`, `suggestions`, `mock_data`, `health`)
- `app/core/` - config, db, security, assessment, auto-population
- `app/schemas/` - API request/response models
- `api/index.py` - Vercel entrypoint

## Deployment (Vercel)

Required env vars:
- `MONGODB_URI`
- `MONGODB_DB_NAME`

Optional:
- `DEBUG`
- `LLM_API_KEY`

Note: `environment.env` is local-only. Configure env vars in Vercel dashboard.
