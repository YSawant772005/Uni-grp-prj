"""Consistent error envelope (API_Contract §4.4) and exception handlers."""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("uni.api")


class ErrorDetail(BaseModel):
    field: str | None = None
    code: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """Application-level error mapped directly to the envelope."""

    def __init__(self, status_code: int, code: str, message: str, details: list[dict] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


def envelope(request: Request, status_code: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    body = {"code": code, "message": message, "request_id": rid, "details": details or []}
    return JSONResponse(status_code=status_code, content={"error": body})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return envelope(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return envelope(request, exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(p) for p in err["loc"] if p not in ("body", "query")),
                "code": err["type"],
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return envelope(request, 422, "VALIDATION_ERROR", "One or more fields are invalid.", details)

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(request: Request, exc: RateLimitExceeded):
        return envelope(request, 429, "RATE_LIMITED", "Too many requests. Please try again later.")

    @app.exception_handler(IntegrityError)
    async def _integrity_error(request: Request, exc: IntegrityError):
        logger.warning("integrity_error request_id=%s", getattr(request.state, "request_id", None))
        return envelope(request, 409, "CONFLICT", "The request conflicts with existing data.")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled_error request_id=%s", getattr(request.state, "request_id", None))
        return envelope(request, 500, "INTERNAL_ERROR", "An unexpected error occurred.")


def new_request_id() -> str:
    return str(uuid.uuid4())
