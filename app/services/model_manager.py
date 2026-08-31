from enum import StrEnum
from pathlib import Path
from typing import Any


class ModelFormat(StrEnum):
    PYTORCH = "pt"
    ONNX = "onnx"


class ModelLoadError(RuntimeError):
    """Raised when a configured inference model cannot be loaded."""


class ModelNotLoadedError(RuntimeError):
    """Raised when inference is requested before model startup completes."""


class ModelManager:
    """Own one Ultralytics model and hide its on-disk format from callers."""

    def __init__(self, model_path: Path, model_version: str) -> None:
        self.model_path = model_path
        self.model_version = model_version
        self.model_format = self._detect_format(model_path)
        self._model: Any | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self.is_loaded:
            return
        if not self.model_path.is_file():
            raise ModelLoadError(f"Model file does not exist: {self.model_path}")

        try:
            from ultralytics import YOLO

            self._model = YOLO(str(self.model_path))
        except Exception as exc:
            self._model = None
            raise ModelLoadError(
                f"Unable to load {self.model_format.value} model"
            ) from exc

    def predict(self, image: Any) -> Any:
        if self._model is None:
            raise ModelNotLoadedError("The inference model is not loaded")
        return self._model.predict(image, verbose=False)

    @staticmethod
    def _detect_format(model_path: Path) -> ModelFormat:
        try:
            return ModelFormat(model_path.suffix.lower().lstrip("."))
        except ValueError as exc:
            raise ModelLoadError(
                "MODEL_PATH must reference a .pt or .onnx model"
            ) from exc
