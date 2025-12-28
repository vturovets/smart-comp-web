# Smart Comp Web

Monorepo for the Smart Comp web application. The repository contains a FastAPI backend with Celery workers and a React + TypeScript frontend built with Vite.

## Project structure

- `backend/`: FastAPI application with Celery integration and Redis messaging.
- `frontend/`: React UI powered by Vite, React Query, Material UI, and Plotly for charting.
- `docs/`: SRS and SDD documents for the Smart Comp web application.
- `docker-compose.yml`: Local orchestration for the API, Celery worker, Redis, and frontend.

## Prerequisites

- Python 3.10+
- Node.js 20+ and npm
- Docker and Docker Compose (optional, for containerized runs)

## Quick start with Docker Compose

1. Choose your environment files:
   - Docker Compose loads `backend/.env.docker` (points Redis URLs at `redis://redis:6379/*`) and `frontend/.env.example`. Copy these if you need overrides:
     ```bash
     cp backend/.env.docker backend/.env.docker.local
     cp frontend/.env.example frontend/.env
     ```
   - Running services directly on your host uses `backend/.env.example` (Redis at `localhost`).
2. Build and start the stack:
   ```bash
   docker-compose up --build
   ```
3. Access the services:
   - Frontend: http://localhost:5173 (served from the container on port 4173)
   - API: http://localhost:8000 (FastAPI app)
   - Redis: localhost:6379 from your host; inside Compose services refer to it as `redis://redis:6379/*`

## How to launch the application locally (through Intellij IDEA PowerShell)

### Terminal A — start Redis (Docker)

`docker run --name smartcomp-redis -p 6379:6379 -d redis:7`

(Optional sanity check)

`docker exec -it smartcomp-redis redis-cli ping # PONG`

### Terminal B — configure the backend environment install dependencies and start Celery worker

`cp backend/.env.example backend/.env`(keeps Redis URLs pointed at `redis://localhost:6379/*`).
Sanity check:`Select-String -Path backend/.env -Pattern 'APP_REDIS_URL'`should show the localhost URI (`redis://localhost:6379/0`).

From `backend/`(!):`python -m venv .venv`
`cd C:\...\smart-comp-web .\.venv\Scripts\Activate.ps1`
`pip install path\to\smart_comp-0.1.0-py3-none-any.whl`
`pip install -e .[dev]`

`.\celery_worker.ps1`
Sanity check: the worker log should show it has connected to Redis and is “ready” (look for the “ready” banner in the console).

> If PowerShell blocks scripts, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Terminal C — start FastAPI server (Uvicorn)

From `backend/`(same venv):`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
Sanity check:`curl http://localhost:8000/api/health` should return `{"status":"ok"}` since `/health`is mounted under the`/api`prefix by default.

### Terminal D — Install and run the Vite dev server

From `frontend/`:`npm install` then `npm run dev -- --host --port 5173` (port aligns with the default CORS origin).
Sanity check: open http://localhost:5173 in a browser; the network tab should show a successful GET to `/api/health` (200 OK). You can also `curl -I http://localhost:5173` to confirm the dev server is serving content.

## Backend tests and linting:

```bash
pytest
ruff check .
ruff format .
```

## Frontend tests and linting:

```bash
npm test            # runs Vitest suite
npm run test:ui     # component tests
npm run test:e2e    # end-to-end tests
npm run lint        # ESLint with zero warnings allowed
```

Set `VITE_API_BASE_URL` in `frontend/.env` (default: `http://localhost:8000`) to point the UI at your API instance.

## Environment variables

- Backend defaults live in `backend/.env.example` (CORS origins, Redis URLs, storage root, task queue, and upload limits) for running the API directly on your host. Docker Compose uses `backend/.env.docker`, which swaps Redis URLs to `redis://redis:6379/*` so the API and worker connect to the Redis service container.
- Frontend defaults live in `frontend/.env.example` and configure the API base URL for the UI.
