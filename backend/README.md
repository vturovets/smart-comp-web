# Smart Comp Backend

FastAPI service scaffolded for the Smart Comp web application with Celery-ready configuration.

## Development

Create a virtual environment and install the project with dev extras:

```bash
python -m venv .venv
source .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

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
```

Run tests and linting:

```bash
pytest
ruff check .
ruff format .
```

Environment variables can be set in a `.env` file; see `.env.example` for defaults.
