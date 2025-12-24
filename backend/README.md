# Smart Comp Backend

FastAPI service scaffolded for the Smart Comp web application with Celery-ready configuration.

## Development

Create a virtual environment and install the project with dev extras:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Run the API locally:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the Celery worker locally (requires Redis):

```bash
celery -A app.worker.celery_app worker --loglevel=INFO
```

Run tests and linting:

```bash
pytest
ruff check .
ruff format .
```

Environment variables can be set in a `.env` file; see `.env.example` for defaults.
