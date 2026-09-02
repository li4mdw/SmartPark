from dataclasses import dataclass
import logging
from typing import Protocol

from app.errors import ApplicationError
from app.infrastructure.concurrency import InferenceExecutor
from app.services.camera_client import (
    CameraClientError,
    CameraTimeoutError,
    CameraUnavailableError,
    InvalidCameraResponseError,
)
from app.services.inference import InferenceError, InferenceService


logger = logging.getLogger(__name__)


class CameraSource(Protocol):
    async def take_photo(self, carpark_id: str): ...


class CarparkLookup(Protocol):
    def exists(self, carpark_id: str) -> bool: ...


class AnnotationStatusWriter(Protocol):
    async def save_latest(self, **status) -> None: ...


@dataclass(frozen=True, slots=True)
class AnnotationResult:
    carpark_id: str
    image: bytes


class AnnotationService:
    def __init__(
        self,
        camera_client: CameraSource,
        inference_service: InferenceService,
        carpark_registry: CarparkLookup,
        inference_executor: InferenceExecutor,
        status_repository: AnnotationStatusWriter,
    ) -> None:
        self._camera_client = camera_client
        self._inference_service = inference_service
        self._carpark_registry = carpark_registry
        self._inference_executor = inference_executor
        self._status_repository = status_repository

    async def annotate(self, carpark_id: str) -> AnnotationResult:
        if not self._carpark_registry.exists(carpark_id):
            raise ApplicationError(
                status_code=404,
                code="carpark_not_found",
                message="The requested car park does not exist",
            )

        try:
            photo = await self._camera_client.take_photo(carpark_id)
        except CameraTimeoutError as exc:
            raise ApplicationError(
                status_code=504,
                code="camera_timeout",
                message="The car-park camera timed out",
            ) from exc
        except InvalidCameraResponseError as exc:
            raise ApplicationError(
                status_code=502,
                code="invalid_camera_response",
                message="The car-park camera returned an invalid response",
            ) from exc
        except (CameraUnavailableError, CameraClientError) as exc:
            raise ApplicationError(
                status_code=503,
                code="camera_unavailable",
                message="The car-park camera is unavailable",
            ) from exc

        try:
            inference_result = await self._inference_executor.run(
                self._inference_service.predict,
                photo.content,
                include_annotation=True,
            )
        except InferenceError as exc:
            raise ApplicationError(
                status_code=500,
                code="inference_failed",
                message="The image could not be processed",
            ) from exc

        if inference_result.annotated_image is None:
            raise ApplicationError(
                status_code=500,
                code="annotation_failed",
                message="The annotated image could not be generated",
            )

        try:
            await self._status_repository.save_latest(
                carpark_id=photo.carpark_id,
                available_spaces=inference_result.available_spaces,
                confidence_score=inference_result.confidence_score,
                inference_ms=inference_result.inference_ms,
                model_version=inference_result.model_version,
            )
        except Exception:
            # An operational-store outage must not discard a completed annotation.
            logger.exception(
                "carpark_status_write_failed",
                extra={"carpark_id": photo.carpark_id},
            )

        return AnnotationResult(
            carpark_id=photo.carpark_id,
            image=inference_result.annotated_image,
        )
