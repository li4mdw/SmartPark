from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI

from app.api.core import router as core_router
from app.api.dashboard import router as dashboard_router
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.operator import router as operator_router
from app.infrastructure.http import create_http_client
from app.infrastructure.concurrency import InferenceExecutor
from app.infrastructure.logging import configure_logging, request_log_context
from app.infrastructure.redis import create_redis_client
from app.infrastructure.settings import Settings
from app.repositories.carpark_status import CarparkStatusRepository
from app.repositories.request_logs import RequestLogRepository
from app.repositories.search_cache import SearchCacheRepository
from app.services.camera_client import CameraClient
from app.services.annotation import AnnotationService
from app.services.carpark_registry import CarparkRegistry
from app.services.carpark_search import CarparkSearchService
from app.services.inference import InferenceService
from app.services.model_manager import ModelManager
from app.services.operator import OperatorService


logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    model_manager: ModelManager | None = None,
    redis_client: Any | None = None,
) -> FastAPI:
    app_settings = settings or Settings.from_environment()
    inference_model = model_manager or ModelManager(
        app_settings.model_path,
        app_settings.model_version,
    )
    http_client = create_http_client(app_settings)
    camera_client = CameraClient(
        http_client,
        app_settings.max_image_bytes,
        max_concurrent_requests=app_settings.camera_concurrency,
    )
    carpark_registry = CarparkRegistry(app_settings.carpark_count)
    inference_executor = InferenceExecutor(app_settings.inference_concurrency)
    shared_redis = redis_client or create_redis_client(app_settings.redis_url)
    request_log_repository = RequestLogRepository(shared_redis)
    status_repository = CarparkStatusRepository(shared_redis)
    search_cache_repository = SearchCacheRepository(
        shared_redis,
        app_settings.search_cache_ttl_seconds,
        app_settings.model_version,
    )
    operator_service = OperatorService(
        carpark_registry,
        status_repository,
        request_log_repository,
        app_settings.recent_user_window_seconds,
    )
    inference_service = InferenceService(
        inference_model,
        available_class_id=app_settings.available_class_id,
        max_image_bytes=app_settings.max_image_bytes,
    )
    annotation_service = AnnotationService(
        camera_client,
        inference_service,
        carpark_registry,
        inference_executor,
        status_repository,
    )
    carpark_search_service = CarparkSearchService(
        carpark_registry,
        camera_client,
        inference_service,
        inference_executor,
        app_settings.search_timeout_seconds,
        status_repository,
        search_cache_repository,
    )
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = False
        logger.info(
            "application_starting",
            extra={"environment": app_settings.environment},
        )

        try:
            await shared_redis.ping()
            inference_model.load()
            app.state.model_manager = inference_model
            app.state.camera_client = camera_client
            app.state.carpark_registry = carpark_registry
            app.state.inference_service = inference_service
            app.state.inference_executor = inference_executor
            app.state.annotation_service = annotation_service
            app.state.carpark_search_service = carpark_search_service
            app.state.redis = shared_redis
            app.state.request_log_repository = request_log_repository
            app.state.carpark_status_repository = status_repository
            app.state.search_cache_repository = search_cache_repository
            app.state.operator_service = operator_service
            app.state.ready = True
            logger.info(
                "application_ready",
                extra={
                    "model_version": inference_model.model_version,
                    "model_format": inference_model.model_format.value,
                    "carpark_count": carpark_registry.count,
                    "camera_concurrency": app_settings.camera_concurrency,
                    "inference_concurrency": inference_executor.max_concurrency,
                    "search_cache_ttl_seconds": (
                        app_settings.search_cache_ttl_seconds
                    ),
                },
            )
            yield
        finally:
            app.state.ready = False
            await http_client.aclose()
            await shared_redis.aclose()
            logger.info("application_stopping")

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.ready = False

    @app.middleware("http")
    async def observe_request(request, call_next):
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = (
            supplied_request_id
            if 1 <= len(supplied_request_id) <= 128
            else str(uuid4())
        )
        user_uuid = request.query_params.get("uuid")
        if user_uuid is not None and not 1 <= len(user_uuid) <= 128:
            user_uuid = None
        request.state.request_id = request_id
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

            response.headers["x-request-id"] = request_id
            duration_ms = (perf_counter() - started) * 1000

            core_routes = {"/api/find-carparks", "/api/annotate-carpark"}
            if request.url.path in core_routes:
                try:
                    await request_log_repository.record_request(
                        request_id=request_id,
                        uuid=user_uuid,
                        route=request.url.path,
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                    )
                except Exception:
                    logger.exception("request_log_write_failed")

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

    app.include_router(core_router)
    app.include_router(health_router)
    app.include_router(operator_router)
    app.include_router(dashboard_router)
    register_exception_handlers(app)
    return app


app = create_app()
