import base64
from pathlib import Path

from fastapi.testclient import TestClient

from camera_simulator.image_repository import ImageRepository
from camera_simulator.main import create_app
from camera_simulator.settings import CameraSettings


JPEG_BYTES = b"\xff\xd8test-camera-image\xff\xd9"
PNG_BYTES = b"\x89PNG\r\n\x1a\ntest-camera-image"


def make_client(dataset_path: Path) -> TestClient:
    settings = CameraSettings(dataset_path=dataset_path, log_level="CRITICAL")
    return TestClient(create_app(settings))


def test_take_photo_returns_image_and_echoes_carpark_id(tmp_path: Path) -> None:
    (tmp_path / "snapshot.jpg").write_bytes(JPEG_BYTES)

    response = make_client(tmp_path).get(
        "/api/takephoto",
        params={"carpark_id": "CBD_001"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["carpark_id"] == "CBD_001"
    assert payload["status"] == "success"
    assert payload["media_type"] == "image/jpeg"
    assert base64.b64decode(payload["image_base64"]) == JPEG_BYTES
    assert response.headers["x-request-id"]


def test_camera_preserves_supplied_request_id(tmp_path: Path) -> None:
    (tmp_path / "snapshot.jpg").write_bytes(JPEG_BYTES)

    response = make_client(tmp_path).get(
        "/api/takephoto",
        params={"carpark_id": "CBD_001"},
        headers={"x-request-id": "trace-123"},
    )

    assert response.headers["x-request-id"] == "trace-123"


def test_take_photo_rejects_invalid_carpark_id(tmp_path: Path) -> None:
    (tmp_path / "snapshot.jpg").write_bytes(JPEG_BYTES)

    response = make_client(tmp_path).get(
        "/api/takephoto",
        params={"carpark_id": "not-a-carpark"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_take_photo_returns_503_for_empty_dataset(tmp_path: Path) -> None:
    response = make_client(tmp_path).get(
        "/api/takephoto",
        params={"carpark_id": "CBD_002"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "image_unavailable"


def test_repository_ignores_unsupported_files(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not an image", encoding="utf-8")
    (tmp_path / "snapshot.png").write_bytes(PNG_BYTES)

    image = ImageRepository(tmp_path).take_random()

    assert image.content == PNG_BYTES
    assert image.media_type == "image/png"
