from types import SimpleNamespace

import pytest

from app.errors import ApplicationError
from app.services.annotation import AnnotationService
from app.services.camera_client import CameraPhoto, CameraTimeoutError


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
        return SimpleNamespace(annotated_image=b"annotated-image")


class FakeCarparkRegistry:
    def __init__(self, valid: bool = True) -> None:
        self.valid = valid

    def exists(self, carpark_id: str) -> bool:
        return self.valid


@pytest.mark.anyio
async def test_annotation_service_combines_camera_and_inference() -> None:
    service = AnnotationService(
        FakeCameraClient(), FakeInferenceService(), FakeCarparkRegistry()
    )

    result = await service.annotate("CBD_004")

    assert result.carpark_id == "CBD_004"
    assert result.image == b"annotated-image"


@pytest.mark.anyio
async def test_annotation_service_maps_camera_timeout() -> None:
    class TimedOutCamera:
        async def take_photo(self, carpark_id: str):
            raise CameraTimeoutError("timeout")

    service = AnnotationService(
        TimedOutCamera(), FakeInferenceService(), FakeCarparkRegistry()
    )

    with pytest.raises(ApplicationError) as error:
        await service.annotate("CBD_004")

    assert error.value.status_code == 504
    assert error.value.code == "camera_timeout"


@pytest.mark.anyio
async def test_annotation_service_requires_annotated_image() -> None:
    class MissingAnnotationInference:
        def predict(self, image: bytes, *, include_annotation: bool = False):
            return SimpleNamespace(annotated_image=None)

    service = AnnotationService(
        FakeCameraClient(), MissingAnnotationInference(), FakeCarparkRegistry()
    )

    with pytest.raises(ApplicationError) as error:
        await service.annotate("CBD_004")

    assert error.value.code == "annotation_failed"


@pytest.mark.anyio
async def test_annotation_service_rejects_unknown_carpark_before_camera_call() -> None:
    class CameraMustNotBeCalled:
        async def take_photo(self, carpark_id: str):
            raise AssertionError("Camera should not be called for an unknown car park")

    service = AnnotationService(
        CameraMustNotBeCalled(),
        FakeInferenceService(),
        FakeCarparkRegistry(valid=False),
    )

    with pytest.raises(ApplicationError) as error:
        await service.annotate("CBD_999")

    assert error.value.status_code == 404
    assert error.value.code == "carpark_not_found"
