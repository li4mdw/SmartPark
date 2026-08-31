from dataclasses import dataclass
from functools import partial
from typing import Protocol

import anyio

from app.errors import ApplicationError
from app.services.camera_client import (
    CameraClientError,
    CameraTimeoutError,
    CameraUnavailableError,
    InvalidCameraResponseError,
)
from app.services.inference import InferenceError, InferenceService


class CameraSource(Protocol):
    async def take_photo(self, carpark_id: str): ...


class CarparkLookup(Protocol):
    def exists(self, carpark_id: str) -> bool: ...


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
    ) -> None:
        self._camera_client = camera_client
        self._inference_service = inference_service
        self._carpark_registry = carpark_registry

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
            inference_result = await anyio.to_thread.run_sync(
                partial(
                    self._inference_service.predict,
                    photo.content,
                    include_annotation=True,
                )
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

        return AnnotationResult(
            carpark_id=photo.carpark_id,
            image=inference_result.annotated_image,
        )
