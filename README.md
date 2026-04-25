# be
Backend app on FastAPI for ealyeco.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. (Optional) add env values:

```bash
cp environment.example.env environment.env
```

4. Add a JWT signing secret locally (required for auth endpoints; pick one approach):

```bash
cp secrets.example.env secrets.local.env
```

Or set it only for your shell session:

```bash
export JWT_SECRET_KEY="replace-with-strong-random-secret"
```

The API can start without this, but `signup`, `signin`, and token validation will not work until it is set.

5. Run the API:

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
