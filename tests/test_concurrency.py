import base64
import threading
import time
from types import SimpleNamespace

import anyio
import httpx
import pytest

from app.errors import ApplicationError
from app.infrastructure.concurrency import InferenceExecutor
from app.services.camera_client import CameraClient, CameraPhoto
from app.services.carpark_search import CarparkSearchService
from tests.fakes import EmptySearchCache, RecordingStatusRepository


class Registry:
    ids = tuple(f"CBD_{number:03d}" for number in range(1, 11))

    @property
    def count(self) -> int:
        return len(self.ids)

    def sample(self, count: int) -> tuple[str, ...]:
        return self.ids[:count]


class TrackingCamera:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0

    async def take_photo(self, carpark_id: str) -> CameraPhoto:
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            await anyio.sleep(0.03)
            return CameraPhoto(carpark_id, carpark_id.encode(), "image/jpeg")
        finally:
            self.active -= 1


class TrackingInference:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self._lock = threading.Lock()

    def predict(self, image: bytes, *, include_annotation: bool = False):
        with self._lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        try:
            time.sleep(0.04)
            return SimpleNamespace(
                available_spaces=int(image.decode().split("_")[1]),
                confidence_score=0.9,
                inference_ms=40.0,
                model_version="test-v1",
            )
        finally:
            with self._lock:
                self.active -= 1


@pytest.mark.anyio
async def test_search_fetches_cameras_concurrently_and_bounds_inference() -> None:
    camera = TrackingCamera()
    inference = TrackingInference()
    service = CarparkSearchService(
        Registry(),
        camera,
        inference,
        InferenceExecutor(max_concurrency=2),
        search_timeout_seconds=5.0,
        status_repository=RecordingStatusRepository(),
        search_cache=EmptySearchCache(),
    )

    result = await service.find("concurrency-user", 3)

    assert camera.maximum_active > 1
    assert inference.maximum_active == 2
    assert len(result.results) == 3
    assert [item.carpark_id for item in result.results] == [
        "CBD_006",
        "CBD_005",
        "CBD_004",
    ]


@pytest.mark.anyio
async def test_search_enforces_overall_timeout() -> None:
    class SlowCamera:
        async def take_photo(self, carpark_id: str):
            await anyio.sleep(1)

    service = CarparkSearchService(
        Registry(),
        SlowCamera(),
        TrackingInference(),
        InferenceExecutor(1),
        search_timeout_seconds=0.01,
        status_repository=RecordingStatusRepository(),
        search_cache=EmptySearchCache(),
    )

    with pytest.raises(ApplicationError) as error:
        await service.find("timeout-user", 1)

    assert error.value.status_code == 504
    assert error.value.code == "search_timeout"


@pytest.mark.anyio
async def test_camera_client_enforces_shared_request_limit() -> None:
    active = 0
    maximum_active = 0
    lock = anyio.Lock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, maximum_active
        async with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        try:
            await anyio.sleep(0.03)
            carpark_id = request.url.params["carpark_id"]
            return httpx.Response(
                200,
                json={
                    "carpark_id": carpark_id,
                    "status": "success",
                    "msg": "success",
                    "media_type": "image/jpeg",
                    "image_base64": base64.b64encode(b"image").decode(),
                },
            )
        finally:
            async with lock:
                active -= 1

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://camera.test",
    )
    camera = CameraClient(
        http_client,
        max_image_bytes=1024,
        max_concurrent_requests=2,
    )

    async def request_photo(number: int) -> None:
        await camera.take_photo(f"CBD_{number:03d}")

    try:
        async with anyio.create_task_group() as task_group:
            for number in range(1, 7):
                task_group.start_soon(request_photo, number)
    finally:
        await http_client.aclose()

    assert maximum_active == 2


@pytest.mark.parametrize("limit", [0, -1])
def test_inference_executor_rejects_invalid_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        InferenceExecutor(limit)
