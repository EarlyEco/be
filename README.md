# be
Backend app on FastAPI for ealyeco.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r app/requirements.txt
```

3. (Optional) add env values:

```bash
cp .env.example .env
```

4. Run the API:

```bash
uvicorn app.main:app --reload
```

## Endpoints

- `GET /api/v1/health` - basic health check
- `GET /api/v1/health/db` - MongoDB connectivity check
