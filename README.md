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

## Backend development

Create a virtual environment, install dependencies, and run the API:


## Run the API locally (through Intellij IDEA PowerShell):

### Terminal A — start Redis (Docker)

`docker run --name smartcomp-redis -p 6379:6379 -d redis:7`

(Optional sanity check)

`docker exec -it smartcomp-redis redis-cli ping # PONG`

### Terminal B — start Celery worker

`cd C:\...\smart-comp-web .\.venv\Scripts\Activate.ps1`

`cd backend`

`.\celery_worker.ps1`

> If PowerShell blocks scripts, run once:

`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Terminal C — start the API (Uvicorn)

`cd C:\...\smart-comp-web .\.venv\Scripts\Activate.ps1`

`cd backend`

`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

### Terminal D — start the frontend

`cd frontend`

`npm run dev`


## Backend tests and linting:

```bash
pytest
ruff check .
ruff format .
```

## Frontend development

Install dependencies and start Vite:

```bash
cd frontend
npm install
npm run dev
```

Frontend tests and linting:

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
