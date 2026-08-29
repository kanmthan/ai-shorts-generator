"""Application-level exceptions and their HTTP handlers.

Business logic raises the typed errors below; :func:`register_exception_handlers`
wires them into FastAPI so every error leaves the API as a consistent JSON body:

    {"error": {"code": "NOT_FOUND", "message": "Project not found", "details": {...}}}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.logging_config import get_logger

logger = get_logger("exceptions")


class AppError(Exception):
    """Base class for all expected application errors.

    Attributes:
        message: Human-readable description.
        code: Stable machine-readable error code.
        status_code: HTTP status to return.
        details: Optional structured context.
    """

    code: str = "APP_ERROR"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details: dict[str, Any] = details or {}

    def to_response(self) -> JSONResponse:
        """Render this error as a JSON response."""
        return JSONResponse(
            status_code=self.status_code,
            content={
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "details": self.details,
                }
            },
        )


class NotFoundError(AppError):
    """A requested resource does not exist (HTTP 404)."""

    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    """The request conflicts with current state, e.g. a duplicate (HTTP 409)."""

    code = "CONFLICT"
    status_code = status.HTTP_409_CONFLICT


class ValidationError(AppError):
    """Input failed a business-rule validation (HTTP 422)."""

    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class ExternalServiceError(AppError):
    """An upstream dependency failed or misbehaved (HTTP 502)."""

    code = "EXTERNAL_SERVICE_ERROR"
    status_code = status.HTTP_502_BAD_GATEWAY


class RateLimitedError(AppError):
    """The caller (or an upstream provider) hit a rate limit (HTTP 429)."""

    code = "RATE_LIMITED"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


def register_exception_handlers(app: FastAPI) -> None:
    """Attach JSON exception handlers to the FastAPI ``app``."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        log = logger.warning if exc.status_code < 500 else logger.error
        log("AppError %s (%s): %s", exc.code, exc.status_code, exc.message)
        return exc.to_response()

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info("Request validation failed: %s", exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        )
