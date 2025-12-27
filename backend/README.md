# Smart Comp Backend

FastAPI service scaffolded for the Smart Comp web application with Celery-ready configuration.

## Development

Create a virtual environment and install the project with dev extras:

```bash
python -m venv .venv
source .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Run tests and linting:

```bash
pytest
ruff check .
ruff format .
```

Environment variables can be set in a `.env` file; see `.env.example` for defaults.
