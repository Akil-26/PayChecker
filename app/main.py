"""Production-grade application factory.

Assembles the FastAPI application with:
- Environment-aware docs (disabled in production)
- API key authentication middleware
- CORS for dashboard access
- Request timing header
- Structured error responses
- Database table creation on startup
- Webhook + API routes
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.errors import PaycheckerError
from app.core.logging import configure_logging, get_logger

logger = get_logger("api")

RESPONSE_TIME_HEADER = "X-Response-Time-ms"


def _build_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        from app.core.container import get_clock
        from app.db.base import Base
        from app.db.session import get_engine, ping_db
        import app.models  # noqa: F401 — registers all ORM models

        engine = get_engine()
        if settings.is_production:
            # Production schema is owned by Alembic migrations (see migrations/),
            # not by this app creating tables on the fly. Run
            #   alembic upgrade head
            # as a deploy step before starting the app.
            logger.info("Production mode: schema managed by Alembic migrations (not auto-created).")
        else:
            Base.metadata.create_all(bind=engine)

        db_ok = ping_db()
        clock = get_clock(settings)

        logger.info(
            "%s v%s started | env=%s | db=%s | clock=%s | executor=%s",
            settings.app_name,
            settings.version,
            settings.environment,
            "ok" if db_ok else "UNREACHABLE",
            clock.now().isoformat(),
            settings.action_executor_impl,
        )

        if settings.is_production:
            if not settings.api_key_secret:
                logger.error("CRITICAL: API_KEY_SECRET is not set — all requests will be rejected")
            if not settings.razorpay_configured:
                logger.warning(
                    "Razorpay credentials not set — recovery actions will use simulator"
                )
            logger.info(
                "Production mode: docs disabled=%s | razorpay=%s",
                settings.disable_docs_in_production,
                "configured" if settings.razorpay_configured else "not configured",
            )
        else:
            logger.info(
                "Development mode: docs enabled | auth bypassed | "
                "demo/simulate endpoints active"
            )

        yield

        logger.info("%s shutting down", settings.app_name)

    return lifespan


def _envelope(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _describe_validation_error(exc: RequestValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        location = [str(item) for item in error.get("loc", []) if item != "body"]
        field = ".".join(location) or "request"
        parts.append(f"{field}: {error.get('msg', 'invalid value')}")
    return "; ".join(parts) or "Request validation failed."


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.version,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=_build_lifespan(settings),
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ── Request timing ────────────────────────────────────────────────────
    @app.middleware("http")
    async def add_response_time_header(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.headers[RESPONSE_TIME_HEADER] = f"{elapsed_ms:.2f}"
        logger.debug(
            "%s %s → %s in %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    # ── Error handlers ────────────────────────────────────────────────────
    @app.exception_handler(PaycheckerError)
    async def handle_domain_error(_: Request, exc: PaycheckerError) -> JSONResponse:
        logger.info("domain error %s: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.http_status,
            content=_envelope(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("VALIDATION_ERROR", _describe_validation_error(exc)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_envelope("INTERNAL_ERROR", "An unexpected internal error occurred."),
        )

    # ── Routes ────────────────────────────────────────────────────────────
    from app.api.router import api_router, root_router

    app.include_router(root_router)
    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
