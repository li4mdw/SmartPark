import base64
import logging

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.infrastructure.logging import JsonFormatter
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
