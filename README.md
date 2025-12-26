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

1. Copy environment defaults if you want to customize them:
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```
2. Build and start the stack:
   ```bash
   docker-compose up --build
   ```
3. Access the services:
   - Frontend: http://localhost:5173 (served from the container on port 4173)
   - API: http://localhost:8000 (FastAPI app)
   - Redis: localhost:6379

## Backend development

Create a virtual environment, install dependencies, and run the API:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the Celery worker (requires Redis):

```bash
celery -A app.worker.celery_app worker --loglevel=INFO
```

Backend tests and linting:

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

- Backend defaults live in `backend/.env.example` (CORS origins, Redis URLs, storage root, task queue, and upload limits).
- Frontend defaults live in `frontend/.env.example` and configure the API base URL for the UI.
