from io import BytesIO
from statistics import fmean
from time import perf_counter
from typing import Any, Protocol

from PIL import Image, UnidentifiedImageError

from app.schemas.inference import Detection, InferenceResult


class InferenceError(RuntimeError):
    """Raised when an image cannot be safely processed."""


class PredictionModel(Protocol):
    model_version: str

    def predict(self, image: Any) -> Any: ...


class InferenceService:
    def __init__(
        self,
        model_manager: PredictionModel,
        available_class_id: int = 0,
        max_image_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self._model_manager = model_manager
        self._available_class_id = available_class_id
        self._max_image_bytes = max_image_bytes

    def predict(
        self,
        image_bytes: bytes,
        *,
        include_annotation: bool = False,
    ) -> InferenceResult:
        image = self._decode_image(image_bytes)

        started = perf_counter()
        try:
            predictions = self._model_manager.predict(image)
            result = predictions[0]
        except Exception as exc:
            raise InferenceError("Model inference failed") from exc
        elapsed_ms = (perf_counter() - started) * 1000

        detections = self._read_detections(result)
        available_confidences = [
            detection.confidence
            for detection in detections
            if detection.class_id == self._available_class_id
        ]
        inference_ms = self._reported_inference_ms(result, elapsed_ms)
        annotation = self._render_annotation(result) if include_annotation else None

        return InferenceResult(
            available_spaces=len(available_confidences),
            confidence_score=(
                round(fmean(available_confidences), 4)
                if available_confidences
                else 0.0
            ),
            inference_ms=round(inference_ms, 2),
            model_version=self._model_manager.model_version,
            detections=detections,
            annotated_image=annotation,
        )

    def _decode_image(self, image_bytes: bytes) -> Image.Image:
        if not image_bytes:
            raise InferenceError("Image is empty")
        if len(image_bytes) > self._max_image_bytes:
            raise InferenceError("Image exceeds the configured size limit")

        try:
            image = Image.open(BytesIO(image_bytes))
            image.load()
            return image.convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise InferenceError("Image data is invalid") from exc

    @staticmethod
    def _read_detections(result: Any) -> tuple[Detection, ...]:
        detections: list[Detection] = []
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            coordinates = tuple(round(value) for value in box.xyxy[0].tolist())
            if len(coordinates) != 4:
                raise InferenceError("Model returned invalid bounding-box coordinates")
            detections.append(
                Detection(
                    class_id=class_id,
                    label=str(result.names[class_id]),
                    confidence=round(float(box.conf[0].item()), 4),
                    coordinates=coordinates,
                )
            )
        return tuple(detections)

    @staticmethod
    def _reported_inference_ms(result: Any, fallback_ms: float) -> float:
        speed = getattr(result, "speed", None)
        if isinstance(speed, dict) and isinstance(speed.get("inference"), (int, float)):
            return float(speed["inference"])
        return fallback_ms

    @staticmethod
    def _render_annotation(result: Any) -> bytes:
        try:
            plotted_bgr = result.plot()
            annotated = Image.fromarray(plotted_bgr[:, :, ::-1])
            output = BytesIO()
            annotated.save(output, format="JPEG", quality=90)
            return output.getvalue()
        except Exception as exc:
            raise InferenceError("Annotated image could not be generated") from exc
