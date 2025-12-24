from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.errors import ApiError, api_error_handler, http_error_handler, request_validation_error_handler
from .api.routes import router as api_router
from .core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.project_name, version=settings.project_version)

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

    return app


app = create_app()
