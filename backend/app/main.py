"""FastAPI application entrypoint.

Wires CORS, exception handlers, logging, rate limiting, the module API routers
and (for local, non-S3 deployments) the ``/media`` static mount for rendered
video output.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.exceptions import register_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.rate_limit import limiter

configure_logging()
logger = get_logger("main")


def register_routers(app: FastAPI) -> None:
    """Register every module API router.

    Each router already carries its own ``/api/v1`` (or ``/api/v1/<module>``)
    prefix, so they are included without an extra prefix.
    """
    from app.routers import auth, dashboard, projects, render_jobs, shorts

    for module in (auth, projects, shorts, render_jobs, dashboard):
        app.include_router(module.router)


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )

    # Rate limiting (shared slowapi limiter — see app.rate_limit).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    register_routers(app)

    # Rendered MP4s are served ONLY through the authenticated, per-user
    # `GET /api/v1/render-jobs/{id}/download` endpoint (FileResponse for local
    # storage, presigned URL for S3). No public StaticFiles mount - the object
    # keys are predictable, so a public mount would expose other users' output.
    if not settings.s3_enabled:
        from app.services.storage import ensure_media_root

        ensure_media_root()

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    logger.info("%s v%s initialised", settings.APP_NAME, settings.APP_VERSION)
    return app


app = create_app()
