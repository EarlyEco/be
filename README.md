# be
Backend app on FastAPI for ealyeco.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your local `environment.env` from the example:

```bash
cp environment.example.env environment.env
```

Then edit `environment.env` and set real values for:

- `MONGODB_URI`
- `MONGODB_DB_NAME`

Optional overrides (otherwise defaults in `app/core/config.py` apply):

- `JWT_ALGORITHM`

For local auth, either add `JWT_SECRET_KEY` to `environment.env` **or** export it in your shell (Vercel should use project env vars instead of committing secrets).

The API can start without `JWT_SECRET_KEY`, but `signup`, `signin`, and token validation will not work until it is available to the process.

4. Run the API:

```bash
uvicorn app.main:app --reload
```

## Endpoints

- `GET /api/v1/health` - basic health check
- `GET /api/v1/health/db` - MongoDB connectivity check
- `POST /api/v1/auth/signup` - register user and create session token
- `POST /api/v1/auth/signin` - authenticate user and create session token
- `GET /api/v1/auth/me` - get current user (requires Bearer token)

## Deploy on Vercel

This repo is configured for Vercel Python runtime.

### Required environment variables in Vercel

- `JWT_SECRET_KEY`
- `MONGODB_URI`
- `MONGODB_DB_NAME`

### Optional environment variables in Vercel

- `DEBUG` (defaults to `false` if unset)

### Deploy steps

1. Push code to GitHub.
2. Import the repo in Vercel.
3. Add the environment variables in Vercel project settings.
4. Deploy.
