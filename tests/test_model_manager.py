from pathlib import Path

import pytest

from app.services.model_manager import ModelFormat, ModelLoadError, ModelManager


def test_model_manager_accepts_pytorch_and_onnx_paths() -> None:
    pytorch = ModelManager(Path("model.pt"), "pt-v1")
    onnx = ModelManager(Path("model.onnx"), "onnx-v1")

    assert pytorch.model_format is ModelFormat.PYTORCH
    assert onnx.model_format is ModelFormat.ONNX


def test_model_manager_rejects_unknown_format() -> None:
    with pytest.raises(ModelLoadError, match=".pt or .onnx"):
        ModelManager(Path("model.invalid"), "invalid-v1")


def test_model_manager_reports_missing_file(tmp_path: Path) -> None:
    manager = ModelManager(tmp_path / "missing.pt", "missing-v1")

    with pytest.raises(ModelLoadError, match="does not exist"):
        manager.load()
