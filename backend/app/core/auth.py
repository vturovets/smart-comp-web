from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.api.errors import ApiError, _build_error_response
from app.core.config import Settings

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    user_id: str
    email: str
    domain: str


def verify_bearer_token(token: str, settings: Settings) -> AuthenticatedUser:
    try:
        info = id_token.verify_oauth2_token(token, GoogleRequest(), settings.google_client_id)
    except Exception as exc:  # pragma: no cover - network/crypto errors are returned to caller
        logger.warning("Failed to verify token: %s", exc)
        raise ApiError(401, "UNAUTHENTICATED", "Invalid or expired bearer token.") from exc

    email = str(info.get("email") or "")
    if "@" not in email:
        raise ApiError(401, "UNAUTHENTICATED", "Token is missing required email claim.")

    domain = email.split("@")[-1].lower()
    return AuthenticatedUser(user_id=email, email=email, domain=domain)


async def authenticate_request(request: Request, settings: Settings):
    credentials: HTTPAuthorizationCredentials | None = await bearer_scheme(request)
    if credentials is None or not credentials.scheme.lower() == "bearer":
        response = _build_error_response(401, "UNAUTHENTICATED", "Bearer token required.")
        response.headers["WWW-Authenticate"] = "Bearer"
        return None, response

    try:
        user = verify_bearer_token(credentials.credentials, settings)
    except ApiError as exc:
        response = _build_error_response(exc.status_code, exc.code, exc.message, details=exc.details)
        if exc.status_code == 401:
            response.headers["WWW-Authenticate"] = "Bearer"
        return None, response

    if settings.allowed_domains and user.domain not in settings.allowed_domains:
        response = _build_error_response(
            403,
            "FORBIDDEN",
            f"Email domain '{user.domain}' is not permitted.",
        )
        return None, response

    return user, None
