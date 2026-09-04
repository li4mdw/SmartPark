import base64
from pathlib import Path

import httpx
import pytest

from app.services.camera_client import (
    CameraClient,
    CameraTimeoutError,
    CameraUnavailableError,
    InvalidCameraResponseError,
)
from camera_simulator.main import create_app as create_camera_app
from camera_simulator.settings import CameraSettings
from app.infrastructure.logging import request_log_context


IMAGE_BYTES = b"camera-image-bytes"


def valid_payload(carpark_id: str = "CBD_001") -> dict[str, str]:
    return {
        "carpark_id": carpark_id,
        "status": "success",
        "msg": "success",
        "media_type": "image/jpeg",
        "image_base64": base64.b64encode(IMAGE_BYTES).decode("ascii"),
    }


def make_client(handler, max_image_bytes: int = 1024) -> CameraClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(
        transport=transport,
        base_url="http://camera.test",
    )
    return CameraClient(http_client, max_image_bytes=max_image_bytes)


@pytest.mark.anyio
async def test_camera_client_returns_valid_photo() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/takephoto"
        assert request.url.params["carpark_id"] == "CBD_001"
        return httpx.Response(200, json=valid_payload())

    photo = await make_client(handler).take_photo("CBD_001")

    assert photo.carpark_id == "CBD_001"
    assert photo.content == IMAGE_BYTES
    assert photo.media_type == "image/jpeg"


@pytest.mark.anyio
async def test_camera_client_forwards_request_context() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-request-id"] == "request-123"
        assert request.headers["x-user-uuid"] == "user-456"
        return httpx.Response(200, json=valid_payload())

    with request_log_context("request-123", "user-456"):
        await make_client(handler).take_photo("CBD_001")


@pytest.mark.anyio
async def test_camera_client_rejects_mismatched_carpark_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=valid_payload("CBD_999"))

    with pytest.raises(InvalidCameraResponseError, match="mismatched"):
        await make_client(handler).take_photo("CBD_001")


@pytest.mark.anyio
async def test_camera_client_rejects_invalid_base64() -> None:
    payload = valid_payload()
    payload["image_base64"] = "not valid base64!"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(InvalidCameraResponseError, match="base64"):
        await make_client(handler).take_photo("CBD_001")


@pytest.mark.anyio
async def test_camera_client_rejects_oversized_image() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=valid_payload())

    with pytest.raises(InvalidCameraResponseError, match="size limit"):
        await make_client(handler, max_image_bytes=5).take_photo("CBD_001")


@pytest.mark.anyio
async def test_camera_client_handles_non_200_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"status": "error"})

    with pytest.raises(CameraUnavailableError, match="HTTP 503"):
        await make_client(handler).take_photo("CBD_001")


@pytest.mark.anyio
async def test_camera_client_handles_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(CameraTimeoutError):
        await make_client(handler).take_photo("CBD_001")


@pytest.mark.anyio
async def test_camera_client_integrates_with_camera_simulator(tmp_path: Path) -> None:
    (tmp_path / "snapshot.jpg").write_bytes(IMAGE_BYTES)
    simulator = create_camera_app(
        CameraSettings(dataset_path=tmp_path, log_level="CRITICAL")
    )
    http_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=simulator),
        base_url="http://camera.test",
    )
    camera_client = CameraClient(http_client, max_image_bytes=1024)

    try:
        photo = await camera_client.take_photo("CBD_007")
    finally:
        await http_client.aclose()

    assert photo.carpark_id == "CBD_007"
    assert photo.content == IMAGE_BYTES
