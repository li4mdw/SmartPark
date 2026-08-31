import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import ApplicationError
from app.schemas.errors import ErrorDetail, ErrorResponse


logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        logger.warning(
            "application_request_failed",
            extra={"path": request.url.path, "error_code": exc.code},
        )
        payload = ErrorResponse(
            status="error",
            msg=exc.message,
            error=ErrorDetail(code=exc.code),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.info(
            "request_validation_failed",
            extra={"path": request.url.path, "validation_errors": exc.errors()},
        )
        payload = ErrorResponse(
            status="error",
            msg="Request validation failed",
            error=ErrorDetail(code="validation_error"),
        )
        return JSONResponse(
            status_code=422,
            content=payload.model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_request_error", extra={"path": request.url.path})
        payload = ErrorResponse(
            status="error",
            msg="An unexpected error occurred",
            error=ErrorDetail(code="internal_error"),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload.model_dump(),
        )
