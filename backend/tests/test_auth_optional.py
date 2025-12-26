from __future__ import annotations

import json

import pytest

from .conftest import build_test_client


def _auth_env(tmp_path):
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    config_file = tmp_path / "config.txt"
    config_file.write_text(
        "[test]\nalpha=0.05\nbootstrap iterations=3\npermutation count=3\n",
        encoding="utf-8",
    )
    return {
        "APP_ENVIRONMENT": "test",
        "APP_AUTH_ENABLED": "true",
        "APP_ALLOWED_DOMAINS": "allowed.com",
        "APP_GOOGLE_CLIENT_ID": "client-id",
        "APP_GOOGLE_CLIENT_SECRET": "client-secret",
        "APP_STORAGE_ROOT": str(storage_root),
        "APP_SMART_COMP_CONFIG_PATH": str(config_file),
    }


def test_auth_disabled_allows_requests(api_client, kw_zip_bytes: bytes) -> None:
    creation = api_client.post(
        "/api/jobs",
        data={"jobType": "BOOTSTRAP_SINGLE", "config": json.dumps({"bootstrapIterations": 1})},
        files={"file1": ("dataset.csv", b"value\n1", "text/csv")},
    )
    assert creation.status_code == 201


def test_auth_enabled_requires_token(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis,
    kw_zip_bytes: bytes,
    tmp_path,
) -> None:
    from app.core import auth as auth_module

    client = build_test_client(monkeypatch, fake_redis, env_overrides=_auth_env(tmp_path))

    missing = client.get("/api/config/defaults")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "UNAUTHENTICATED"

    monkeypatch.setattr(
        auth_module,
        "verify_bearer_token",
        lambda token, settings: auth_module.AuthenticatedUser(
            user_id="user@allowed.com",
            email="user@allowed.com",
            domain="allowed.com",
        ),
    )

    creation = client.post(
        "/api/jobs",
        data={"jobType": "BOOTSTRAP_SINGLE", "config": json.dumps({"bootstrapIterations": 1})},
        files={"file1": ("dataset.csv", b"value\n1", "text/csv")},
        headers={"Authorization": "Bearer valid"},
    )
    assert creation.status_code == 201
    assert creation.json()["jobId"]


def test_domain_allowlist_enforced(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis,
    kw_zip_bytes: bytes,
    tmp_path,
) -> None:
    from app.core import auth as auth_module

    client = build_test_client(monkeypatch, fake_redis, env_overrides=_auth_env(tmp_path))
    monkeypatch.setattr(
        auth_module,
        "verify_bearer_token",
        lambda token, settings: auth_module.AuthenticatedUser(
            user_id="user@other.com",
            email="user@other.com",
            domain="other.com",
        ),
    )

    response = client.get("/api/config/defaults", headers={"Authorization": "Bearer valid"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_job_visibility_is_scoped(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis,
    kw_zip_bytes: bytes,
    tmp_path,
) -> None:
    from app.core import auth as auth_module

    client = build_test_client(monkeypatch, fake_redis, env_overrides=_auth_env(tmp_path))

    def fake_verify(token: str, settings):
        return auth_module.AuthenticatedUser(
            user_id=f"{token}@allowed.com",
            email=f"{token}@allowed.com",
            domain="allowed.com",
        )

    monkeypatch.setattr(auth_module, "verify_bearer_token", fake_verify)

    creation = client.post(
        "/api/jobs",
        data={"jobType": "BOOTSTRAP_SINGLE", "config": json.dumps({"bootstrapIterations": 1})},
        files={"file1": ("dataset.csv", b"value\n1", "text/csv")},
        headers={"Authorization": "Bearer owner"},
    )
    job_id = creation.json()["jobId"]

    unauthorized = client.get(f"/api/jobs/{job_id}", headers={"Authorization": "Bearer intruder"})
    assert unauthorized.status_code == 403
    assert unauthorized.json()["error"]["code"] == "FORBIDDEN"

    authorized = client.get(f"/api/jobs/{job_id}", headers={"Authorization": "Bearer owner"})
    assert authorized.status_code == 200
