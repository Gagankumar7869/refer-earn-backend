import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[list[Any]] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(message)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required", code: str = "UNAUTHORIZED"):
        super().__init__(status_code=401, code=code, message=message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Caller lacks permission", code: str = "FORBIDDEN"):
        super().__init__(status_code=403, code=code, message=message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(status_code=404, code=code, message=message)


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Conflicting operation",
        code: str = "CONFLICT",
        details: Optional[list[Any]] = None,
    ):
        super().__init__(status_code=409, code=code, message=message, details=details)


class ValidationError(AppError):
    def __init__(
        self,
        message: str = "Request validation failure",
        code: str = "VALIDATION_ERROR",
        details: Optional[list[Any]] = None,
    ):
        super().__init__(status_code=422, code=code, message=message, details=details)


def error_payload(code: str, message: str, details: Optional[list[Any]] = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_payload(
                code="VALIDATION_ERROR",
                message="Request validation failure",
                details=details,
            ),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        logger.warning("Database integrity error caught: %s", exc)
        return JSONResponse(
            status_code=409,
            content=error_payload(
                code="CONFLICT",
                message="Database constraint violation or duplicate operation",
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled server error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=error_payload(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected internal server error occurred",
            ),
        )