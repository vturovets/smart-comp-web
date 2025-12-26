from __future__ import annotations

import importlib
from io import BytesIO
from pathlib import Path
from typing import Generator
import zipfile

import pytest
from fastapi.testclient import TestClient

import app.core.config as core_config
from app.core.jobs import JobRepository


def pytest_addoption(parser) -> None:
    # Ensure pytest recognizes asyncio_mode even when pytest-asyncio is not installed.
    parser.addini("asyncio_mode", help="Asyncio plugin mode", default="auto")


class StubRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self._store[key] = str(value)

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    def eval(self, script: str, numkeys: int, *args):
        if numkeys != 1:
            raise ValueError("Expected a single key for semaphore scripts")
        key = args[0]
        if "incr" in script:
            limit = int(args[1])
            current = int(self._store.get(key, "0"))
            if current >= limit:
                return 0
            current += 1
            self._store[key] = str(current)
            return current

        current = int(self._store.get(key, "0"))
        if current <= 0:
            self._store.pop(key, None)
            return 0
        current -= 1
        if current <= 0:
            self._store.pop(key, None)
            return current
        self._store[key] = str(current)
        return current


@pytest.fixture
def fake_redis() -> StubRedis:
    return StubRedis()


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APP_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("APP_JOB_TIMEOUT_SECONDS", "5")

    config_file = tmp_path / "config.txt"
    config_file.write_text(
        "[test]\nalpha=0.05\nbootstrap iterations=3\npermutation count=3\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_SMART_COMP_CONFIG_PATH", str(config_file))

    core_config.get_settings.cache_clear()
    return core_config.get_settings()


@pytest.fixture
def api_client(
    monkeypatch: pytest.MonkeyPatch,
    test_settings,
    fake_redis: StubRedis,
) -> Generator[TestClient, None, None]:
    yield build_test_client(monkeypatch, fake_redis)


def build_test_client(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: StubRedis,
    env_overrides: dict[str, str] | None = None,
) -> TestClient:
    for key, value in (env_overrides or {}).items():
        monkeypatch.setenv(key, value)

    storage_root_env = (env_overrides or {}).get("APP_STORAGE_ROOT")
    if storage_root_env:
        Path(storage_root_env).mkdir(parents=True, exist_ok=True)

    import app.api.dependencies as deps
    import app.worker.celery_app as celery_module
    import app.worker.tasks as worker_tasks
    import app.main as main

    importlib.reload(core_config)
    core_config.get_settings.cache_clear()
    core_config.get_settings()

    importlib.reload(celery_module)
    importlib.reload(worker_tasks)
    importlib.reload(deps)

    monkeypatch.setattr(worker_tasks, "get_redis_client", lambda: fake_redis)
    worker_tasks._cached_redis = fake_redis
    worker_tasks.celery_app.conf.task_always_eager = True
    worker_tasks.celery_app.conf.task_eager_propagates = True

    app_instance = importlib.reload(main).create_app()
    app_instance.dependency_overrides[deps.get_job_repository] = lambda: JobRepository(fake_redis)
    app_instance.dependency_overrides[deps.get_redis_client_dep] = lambda: fake_redis
    return TestClient(app_instance)


@pytest.fixture
def kw_zip_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("GroupA/a1.csv", "value\n1")
        zf.writestr("GroupB/b1.csv", "value\n2")
    return buffer.getvalue()
