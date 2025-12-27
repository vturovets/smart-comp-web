import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse
from prometheus_client import generate_latest
from prometheus_client import REGISTRY as prometheus_registry
from prometheus_client import CONTENT_TYPE_LATEST

from app.core.auth import AuthenticatedUser, authenticate_request
from .api.errors import (
    ApiError,
    _build_error_response,
    api_error_handler,
    http_error_handler,
    request_validation_error_handler,
)
from .api.routes import router as api_router
from .core.config import get_settings
from .core.observability import (
    bind_request_context,
    configure_logging,
    record_request_metrics,
)

logger = logging.getLogger(__name__)


class _RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-ID")
        bind_request_context(request_id, trace_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - start
            record_request_metrics(request.method, request.url.path, 500, duration)
            logger.exception("Unhandled error for %s %s", request.method, request.url.path)
            response = _build_error_response(
                500,
                "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                details={},
            )

        duration = time.perf_counter() - start
        record_request_metrics(request.method, request.url.path, response.status_code, duration)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id or request_id
        return response


class _AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, settings) -> None:  # type: ignore[override]
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        if not self.settings.auth_enabled:
            return await call_next(request)

        if request.url.path in {"/", "/metrics", f"{self.settings.api_prefix}/health"}:
            return await call_next(request)

        user, error_response = await authenticate_request(request, self.settings)
        if error_response:
            return error_response

        assert isinstance(user, AuthenticatedUser)
        request.state.user = user
        return await call_next(request)


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.auth_enabled:
        missing = [
            name
            for name in ("google_client_id", "google_client_secret")
            if not getattr(settings, name)
        ]
        if missing:
            raise RuntimeError(
                "Authentication enabled but missing required settings: " + ", ".join(missing),
            )
        if not settings.allowed_domains:
            raise RuntimeError("Authentication enabled but no allowed_domains configured.")

    configure_logging(logging.DEBUG if settings.debug else logging.INFO)
    app = FastAPI(title=settings.project_name, version=settings.project_version)
    app.add_middleware(_RequestContextMiddleware)
    app.add_middleware(_AuthMiddleware, settings=settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)

    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", tags=["root"])
    def read_root() -> dict[str, str]:
        return {"message": "Smart Comp API"}

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        data = generate_latest(prometheus_registry)
        return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
