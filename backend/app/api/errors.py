from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.observability import get_request_id

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Structured error used for consistent API responses."""

    def __init__(self, status_code: int, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def _build_error_response(status_code: int, code: str, message: str, *, details: dict[str, Any] | None = None) -> JSONResponse:
    request_id = get_request_id(str(uuid4()))
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message, "details": details or {}},
            "requestId": request_id,
        },
    )


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    logger.info("Returning API error %s: %s", exc.code, exc.message)
    return _build_error_response(exc.status_code, exc.code, exc.message, details=exc.details)


async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = exc.detail if isinstance(exc.detail, str) else "HTTP_ERROR"
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _build_error_response(exc.status_code, str(code), message)


async def request_validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _build_error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "REQUEST_VALIDATION_ERROR",
        "Request validation failed.",
        details={"errors": exc.errors()},
    )
