from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.core import router as core_router
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.infrastructure.http import create_http_client
from app.infrastructure.logging import configure_logging
from app.infrastructure.settings import Settings
from app.services.camera_client import CameraClient
from app.services.annotation import AnnotationService
from app.services.carpark_registry import CarparkRegistry
from app.services.carpark_search import CarparkSearchService
from app.services.inference import InferenceService
from app.services.model_manager import ModelManager


logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    model_manager: ModelManager | None = None,
) -> FastAPI:
    app_settings = settings or Settings.from_environment()
    inference_model = model_manager or ModelManager(
        app_settings.model_path,
        app_settings.model_version,
    )
    http_client = create_http_client(app_settings)
    camera_client = CameraClient(http_client, app_settings.max_image_bytes)
    carpark_registry = CarparkRegistry(app_settings.carpark_count)
    inference_service = InferenceService(
        inference_model,
        available_class_id=app_settings.available_class_id,
        max_image_bytes=app_settings.max_image_bytes,
    )
    annotation_service = AnnotationService(
        camera_client,
        inference_service,
        carpark_registry,
    )
    carpark_search_service = CarparkSearchService(
        carpark_registry,
        camera_client,
        inference_service,
    )
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = False
        logger.info(
            "application_starting",
            extra={"environment": app_settings.environment},
        )

        inference_model.load()
        app.state.model_manager = inference_model
        app.state.camera_client = camera_client
        app.state.carpark_registry = carpark_registry
        app.state.inference_service = inference_service
        app.state.annotation_service = annotation_service
        app.state.carpark_search_service = carpark_search_service
        app.state.ready = True
        logger.info(
            "application_ready",
            extra={
                "model_version": inference_model.model_version,
                "model_format": inference_model.model_format.value,
            },
        )

        try:
            yield
        finally:
            app.state.ready = False
            await http_client.aclose()
            logger.info("application_stopping")

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.ready = False
    app.include_router(core_router)
    app.include_router(health_router)
    register_exception_handlers(app)
    return app


app = create_app()
