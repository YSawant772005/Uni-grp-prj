"""FastAPI application factory: middleware, error handlers, routers."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded  # noqa: F401  (registered handler target)

from app.core.config import settings
from app.core.errors import new_request_id, register_error_handlers
from app.core.scheduler import start_scheduler
from app.routers.v1.auth import limiter
from app.routers.v1.router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = start_scheduler()  # None unless ENABLE_SCHEDULER=true
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(
        title="University Shortlisting Tool API",
        version="1.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    register_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or new_request_id()
        request.state.request_id = rid
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        elapsed_ms = (time.perf_counter() - started) * 1000
        logging.getLogger("uni.api").info(
            "%s %s -> %s %.1fms request_id=%s",
            request.method, request.url.path, response.status_code, elapsed_ms, rid,
        )
        return response

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
