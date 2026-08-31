from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Detection:
    class_id: int
    label: str
    confidence: float
    coordinates: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class InferenceResult:
    available_spaces: int
    confidence_score: float
    inference_ms: float
    model_version: str
    detections: tuple[Detection, ...]
    annotated_image: bytes | None = None
