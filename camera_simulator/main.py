import base64
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.infrastructure.logging import (
    JsonFormatter,
    RequestContextFilter,
    request_log_context,
    valid_correlation_id,
)
from camera_simulator.image_repository import ImageRepository, ImageRepositoryError
from camera_simulator.schemas import (
    CameraErrorDetail,
    CameraErrorResponse,
    TakePhotoQuery,
    TakePhotoResponse,
)
from camera_simulator.settings import CameraSettings


logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service_name="camera-simulator"))
    handler.addFilter(RequestContextFilter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def create_app(settings: CameraSettings | None = None) -> FastAPI:
    camera_settings = settings or CameraSettings.from_environment()
    _configure_logging(camera_settings.log_level)
    repository = ImageRepository(camera_settings.dataset_path)

    app = FastAPI(title="SmartPark Camera Simulator", version="0.1.0")
    app.state.image_repository = repository

    @app.middleware("http")
    async def observe_request(request: Request, call_next):
        supplied_request_id = valid_correlation_id(
            request.headers.get("x-request-id")
        )
        request_id = supplied_request_id or str(uuid4())
        user_uuid = valid_correlation_id(request.headers.get("x-user-uuid"))
        started = perf_counter()

        with request_log_context(request_id, user_uuid):
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "http_request_failed",
                    extra={
                        "http_method": request.method,
                        "http_path": request.url.path,
                        "http_status": 500,
                        "duration_ms": round(
                            (perf_counter() - started) * 1000, 2
                        ),
                    },
                )
                raise
            duration_ms = (perf_counter() - started) * 1000
            response.headers["x-request-id"] = request_id
            response.headers["x-content-type-options"] = "nosniff"
            response.headers["x-frame-options"] = "DENY"
            response.headers["cache-control"] = "no-store"
            logger.info(
                "http_request_completed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": request.client.host if request.client else None,
                },
            )
            return response

    def get_repository(request: Request) -> ImageRepository:
        return request.app.state.image_repository

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.info(
            "request_validation_failed",
            extra={"path": request.url.path, "validation_errors": exc.errors()},
        )
        payload = CameraErrorResponse(
            msg="Request validation failed",
            error=CameraErrorDetail(code="validation_error"),
        )
        return JSONResponse(
            status_code=422,
            content=payload.model_dump(),
        )

    @app.get(
        "/api/takephoto",
        response_model=TakePhotoResponse,
        responses={
            422: {"model": CameraErrorResponse},
            status.HTTP_503_SERVICE_UNAVAILABLE: {"model": CameraErrorResponse},
        },
    )
    async def take_photo(
        query: TakePhotoQuery = Depends(),
        image_repository: ImageRepository = Depends(get_repository),
    ) -> TakePhotoResponse | JSONResponse:
        try:
            image = image_repository.take_random()
        except ImageRepositoryError:
            logger.exception(
                "camera_image_unavailable",
                extra={"carpark_id": query.carpark_id},
            )
            payload = CameraErrorResponse(
                msg="Camera image is unavailable",
                error=CameraErrorDetail(code="image_unavailable"),
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=payload.model_dump(),
            )

        logger.info("photo_captured", extra={"carpark_id": query.carpark_id})
        return TakePhotoResponse(
            carpark_id=query.carpark_id,
            media_type=image.media_type,
            image_base64=base64.b64encode(image.content).decode("ascii"),
        )

    return app


app = create_app()
