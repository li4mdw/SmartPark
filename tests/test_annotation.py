from types import SimpleNamespace

import pytest

from app.errors import ApplicationError
from app.infrastructure.concurrency import InferenceExecutor
from app.services.annotation import AnnotationService
from app.services.camera_client import CameraPhoto, CameraTimeoutError
from tests.fakes import RecordingStatusRepository


class FakeCameraClient:
    async def take_photo(self, carpark_id: str) -> CameraPhoto:
        return CameraPhoto(
            carpark_id=carpark_id,
            content=b"source-image",
            media_type="image/jpeg",
        )


class FakeInferenceService:
    def predict(self, image: bytes, *, include_annotation: bool = False):
        assert image == b"source-image"
        assert include_annotation is True
        return SimpleNamespace(
            annotated_image=b"annotated-image",
            available_spaces=4,
            confidence_score=0.9,
            inference_ms=12.0,
            model_version="test-v1",
        )


class FakeCarparkRegistry:
    def __init__(self, valid: bool = True) -> None:
        self.valid = valid

    def exists(self, carpark_id: str) -> bool:
        return self.valid


def make_service(camera, inference, registry=None, status_repository=None) -> AnnotationService:
    return AnnotationService(
        camera,
        inference,
        registry or FakeCarparkRegistry(),
        InferenceExecutor(1),
        status_repository or RecordingStatusRepository(),
    )


@pytest.mark.anyio
async def test_annotation_service_combines_camera_and_inference() -> None:
    statuses = RecordingStatusRepository()
    service = make_service(
        FakeCameraClient(), FakeInferenceService(), status_repository=statuses
    )

    result = await service.annotate("CBD_004")

    assert result.carpark_id == "CBD_004"
    assert result.image == b"annotated-image"
    assert statuses.saved == [
        {
            "carpark_id": "CBD_004",
            "available_spaces": 4,
            "confidence_score": 0.9,
            "inference_ms": 12.0,
            "model_version": "test-v1",
        }
    ]


@pytest.mark.anyio
async def test_annotation_service_maps_camera_timeout() -> None:
    class TimedOutCamera:
        async def take_photo(self, carpark_id: str):
            raise CameraTimeoutError("timeout")

    service = make_service(TimedOutCamera(), FakeInferenceService())

    with pytest.raises(ApplicationError) as error:
        await service.annotate("CBD_004")

    assert error.value.status_code == 504
    assert error.value.code == "camera_timeout"


@pytest.mark.anyio
async def test_annotation_service_requires_annotated_image() -> None:
    class MissingAnnotationInference:
        def predict(self, image: bytes, *, include_annotation: bool = False):
            return SimpleNamespace(
                annotated_image=None,
                available_spaces=0,
                confidence_score=0.0,
                inference_ms=1.0,
                model_version="test-v1",
            )

    service = make_service(FakeCameraClient(), MissingAnnotationInference())

    with pytest.raises(ApplicationError) as error:
        await service.annotate("CBD_004")

    assert error.value.code == "annotation_failed"


@pytest.mark.anyio
async def test_annotation_service_rejects_unknown_carpark_before_camera_call() -> None:
    class CameraMustNotBeCalled:
        async def take_photo(self, carpark_id: str):
            raise AssertionError("Camera should not be called for an unknown car park")

    service = make_service(
        CameraMustNotBeCalled(),
        FakeInferenceService(),
        registry=FakeCarparkRegistry(valid=False),
    )

    with pytest.raises(ApplicationError) as error:
        await service.annotate("CBD_999")

    assert error.value.status_code == 404
    assert error.value.code == "carpark_not_found"
