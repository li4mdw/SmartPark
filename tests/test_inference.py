from io import BytesIO

import numpy as np
from PIL import Image
import pytest

from app.services.inference import InferenceError, InferenceService


class FakeValue:
    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value

    def tolist(self):
        return self._value


class FakeBox:
    def __init__(self, class_id: int, confidence: float, coordinates: list[float]):
        self.cls = [FakeValue(class_id)]
        self.conf = [FakeValue(confidence)]
        self.xyxy = [FakeValue(coordinates)]


class FakeResult:
    names = {0: "empty", 1: "occupied"}
    speed = {"inference": 12.345}

    def __init__(self):
        self.boxes = [
            FakeBox(0, 0.8, [1.2, 2.4, 10.1, 20.9]),
            FakeBox(0, 0.6, [20, 30, 40, 50]),
            FakeBox(1, 0.9, [5, 6, 7, 8]),
        ]

    def plot(self):
        return np.zeros((10, 10, 3), dtype=np.uint8)


class FakeModelManager:
    model_version = "test-v1"

    def predict(self, image):
        assert image.mode == "RGB"
        return [FakeResult()]


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (20, 20), color="white").save(output, format="JPEG")
    return output.getvalue()


def test_inference_counts_available_spaces_and_confidence() -> None:
    service = InferenceService(FakeModelManager(), available_class_id=0)

    result = service.predict(image_bytes())

    assert result.available_spaces == 2
    assert result.confidence_score == 0.7
    assert result.inference_ms == 12.35
    assert result.model_version == "test-v1"
    assert len(result.detections) == 3
    assert result.detections[0].coordinates == (1, 2, 10, 21)
    assert result.annotated_image is None


def test_inference_can_generate_jpeg_annotation() -> None:
    service = InferenceService(FakeModelManager())

    result = service.predict(image_bytes(), include_annotation=True)

    assert result.annotated_image is not None
    assert result.annotated_image.startswith(b"\xff\xd8")


@pytest.mark.parametrize("invalid_image", [b"", b"not-an-image"])
def test_inference_rejects_invalid_images(invalid_image: bytes) -> None:
    service = InferenceService(FakeModelManager())

    with pytest.raises(InferenceError):
        service.predict(invalid_image)


def test_inference_enforces_image_size_limit() -> None:
    service = InferenceService(FakeModelManager(), max_image_bytes=5)

    with pytest.raises(InferenceError, match="size limit"):
        service.predict(image_bytes())
