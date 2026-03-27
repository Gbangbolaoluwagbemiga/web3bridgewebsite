# Portal Backend (FastAPI)

Part 1 foundation for Student Portal backend.

## Includes
- FastAPI app bootstrap
- PostgreSQL connection (SQLAlchemy async, shared DB supported)
- Redis connection
- Alembic migration setup
- Health checks (`/health/live`, `/health/ready`)

## Shared database mode
- The portal service can run against the same PostgreSQL database used by existing services.
- New portal tables are isolated under `POSTGRES_SCHEMA` (default: `portal`).
- This avoids table-name collisions while keeping one physical database.

## Quick start
1. Copy `.env.example` to `.env`
2. Start infra: `docker compose up -d`
3. Install deps: `pip install -r requirements.txt`
4. Run API: `uvicorn app.main:app --reload --port 8100`

## Endpoints
- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`

## Worker operations
- Start worker once (debug): `python -m app.workers.sync --once`
- Start worker continuously (production): `python -m app.workers.sync`
- Worker loop automatically retries on operational failures with exponential backoff.
- Backoff is configured with:
	- `SYNC_WORKER_ERROR_RETRY_BASE_SECONDS` (default: `1`)
	- `SYNC_WORKER_ERROR_RETRY_MAX_SECONDS` (default: `30`)

## Backend integration mode
- Source of truth for onboarding is the DB-coupled cron job in `app.cron.onboard_students`.
- Operational runbook: `docs/portal_integration_runbook.md`

## Production hardening
- In `APP_ENV=production` / `APP_ENV=staging`, configuration validation enforces:
	- `DEBUG=false`
	- Non-default `JWT_SECRET_KEY`
	- Non-default `INTERNAL_API_KEY`
	- Non-default `POSTGRES_PASSWORD`
	- `PORTAL_FRONTEND_URL` must use `https://`
