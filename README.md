# Smart Comp Web

Monorepo for the Smart Comp web application. The repository contains a FastAPI backend with Celery workers and a React + TypeScript frontend built with Vite.

## Project structure

- `backend/`: FastAPI application with Celery integration and Redis messaging.
- `frontend/`: React UI powered by Vite, React Query, Material UI, and Plotly for charting.
- `docs/`: SRS and SDD documents for the Smart Comp web application.
- `docker-compose.yml`: Local orchestration for the API, Celery worker, Redis, and frontend.

## Architecture overview

**Runtime components**

- **Frontend (React + Vite)** – A single-page app in `frontend/` that uses React Query for data fetching and mutation, Material UI for layout, and Plotly for chart rendering. `VITE_API_BASE_URL` points the SPA at the FastAPI host.
- **API (FastAPI)** – Lives in `backend/app`; exposes `/api/*` routes, applies optional Google OAuth-based auth, enforces request/response observability, and streams artifacts. All requests pass through request/trace ID middleware and CORS middleware configured from `backend/app/core/config.py`.
- **Async worker (Celery + Redis)** – Defined in `backend/app/worker`; accepts jobs from the API via Redis, runs Smart-Comp computations, tracks progress in Redis, and writes results/artifacts to disk.
- **Storage** – Per-job directories rooted at `SMARTCOMP_STORAGE_ROOT` (`/tmp/smartcomp` by default) with `input/` and `output/` subfolders. Artifacts such as `results.json`, Plotly JSON traces, cleaned CSVs, and `tool.log` live under `output/`.
- **Messaging** – Redis brokers Celery tasks and stores job metadata (status, progress, cancel flags). Concurrency is guarded with a semaphore keyed in Redis.

**Execution boundaries**

- `backend/app/main.py` wires middleware, the `/metrics` endpoint, and the API router.
- `backend/app/api/routes.py` houses REST endpoints for config defaults, job creation, status, results, artifacts, and cancellation.
- `backend/app/core/job_service.py` orchestrates validation, file handling, Smart-Comp config resolution, and enqueues Celery tasks.
- `backend/app/worker/runner.py` and `backend/app/worker/smart_comp_executor.py` manage worker-side lifecycle, cancellation/timeout checks, and persistence of outputs.

## Application flows

### Frontend workflow

1. On load, the SPA builds an API client with `VITE_API_BASE_URL` and fetches `/api/config/defaults` to hydrate the job form with Smart-Comp defaults.
2. Users choose a job type (descriptive-only, bootstrap single/dual, or Kruskal–Wallis) and upload CSVs or a KW ZIP. Submitting the form POSTs `multipart/form-data` to `/api/jobs` with `jobType`, JSON `config`, and required files.
3. The app stores the returned `jobId`, then React Query polls `/api/jobs/{jobId}` every ~1.5s until the job reaches `COMPLETED` or `FAILED`. Cancel buttons call `/api/jobs/{jobId}/cancel`.
4. When a job completes, the client fetches `/api/jobs/{jobId}/results` for normalized results and `/api/jobs/{jobId}/artifacts` to list downloadable files. Plotly components call `/api/jobs/{jobId}/artifacts/{name}` to load trace JSON or download assets.

### Backend + worker lifecycle

1. **Create job** – `POST /api/jobs` validates payloads (`file1`, `file2`, `kwBundle` depending on `jobType`), merges overrides with Smart-Comp defaults, writes inputs under `SMARTCOMP_STORAGE_ROOT/<jobId>/input`, and enqueues a Celery task. When auth is enabled, the job is associated with the caller’s user ID.
2. **Progress + guarding** – The Celery task (`app.worker.tasks.run_job`) acquires a Redis-backed semaphore to honor `SMARTCOMP_MAX_CONCURRENT_JOBS`, sets status to `RUNNING`, and streams progress updates (percent, step, message) back to Redis. It periodically checks for cancel flags and wall-clock timeouts.
3. **Execution** – `SmartCompExecutor` runs Smart-Comp routines with the resolved config. Artifacts (results JSON/TXT, cleaned CSVs, plots, logs) are written beneath the job’s `output/` directory.
4. **Completion** – On success, status moves to `COMPLETED` and progress reaches 100%. On failure or timeout, status becomes `FAILED`; on cancellation, status becomes `CANCELLED` and the working directory is removed immediately.
5. **Retention** – When `cleanAll=true` in the config, intermediate CSVs are removed after completion. A background cleanup process (see docs) is expected to delete job directories older than `SMARTCOMP_JOB_TTL_HOURS`.

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

## Quick start/terminate the app locally through PS scripts (Windows)
- start Docker Desktop
- to launch: `.\launch-app.ps1`
- to terminate: `.\stop-app.ps1`

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
