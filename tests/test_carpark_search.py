from types import SimpleNamespace

import pytest

from app.errors import ApplicationError
from app.services.camera_client import CameraPhoto, CameraUnavailableError
from app.services.carpark_search import CarparkSearchService


class FakeRegistry:
    def __init__(self, count: int = 10) -> None:
        self.ids = tuple(f"CBD_{number:03d}" for number in range(1, count + 1))
        self.sample_calls: list[int] = []

    @property
    def count(self) -> int:
        return len(self.ids)

    def sample(self, count: int) -> tuple[str, ...]:
        self.sample_calls.append(count)
        return self.ids[:count]


class FakeCameraClient:
    def __init__(self, failing_ids: set[str] | None = None) -> None:
        self.failing_ids = failing_ids or set()
        self.calls: list[str] = []

    async def take_photo(self, carpark_id: str) -> CameraPhoto:
        self.calls.append(carpark_id)
        if carpark_id in self.failing_ids:
            raise CameraUnavailableError("camera failed")
        return CameraPhoto(
            carpark_id=carpark_id,
            content=carpark_id.encode("ascii"),
            media_type="image/jpeg",
        )


class FakeInferenceService:
    RESULTS = {
        "CBD_001": (5, 0.90),
        "CBD_002": (10, 0.80),
        "CBD_003": (10, 0.90),
        "CBD_004": (2, 0.99),
        "CBD_005": (8, 0.95),
        "CBD_006": (10, 0.90),
    }

    def predict(self, image: bytes, *, include_annotation: bool = False):
        assert include_annotation is False
        carpark_id = image.decode("ascii")
        available, confidence = self.RESULTS.get(carpark_id, (1, 0.5))
        return SimpleNamespace(
            available_spaces=available,
            confidence_score=confidence,
            inference_ms=10.0,
        )


@pytest.mark.anyio
async def test_search_queries_exactly_twice_n_and_ranks_results() -> None:
    registry = FakeRegistry()
    camera = FakeCameraClient()
    service = CarparkSearchService(registry, camera, FakeInferenceService())

    result = await service.find("user-123", 3)

    assert registry.sample_calls == [6]
    assert camera.calls == list(registry.ids[:6])
    assert [item.carpark_id for item in result.results] == [
        "CBD_003",
        "CBD_006",
        "CBD_002",
    ]
    assert result.total_inference_ms == 60.0
    assert result.failed_carparks == 0


@pytest.mark.anyio
async def test_search_allows_partial_failure_when_n_results_remain() -> None:
    registry = FakeRegistry()
    camera = FakeCameraClient(failing_ids={"CBD_002"})
    service = CarparkSearchService(registry, camera, FakeInferenceService())

    result = await service.find("user-123", 2)

    assert camera.calls == list(registry.ids[:4])
    assert len(result.results) == 2
    assert result.failed_carparks == 1


@pytest.mark.anyio
async def test_search_fails_when_too_few_results_remain() -> None:
    registry = FakeRegistry()
    camera = FakeCameraClient(
        failing_ids={"CBD_001", "CBD_002", "CBD_003"}
    )
    service = CarparkSearchService(registry, camera, FakeInferenceService())

    with pytest.raises(ApplicationError) as error:
        await service.find("user-123", 2)

    assert camera.calls == list(registry.ids[:4])
    assert error.value.status_code == 503
    assert error.value.code == "insufficient_carpark_results"


@pytest.mark.anyio
async def test_search_rejects_n_when_twice_n_exceeds_range() -> None:
    registry = FakeRegistry(count=10)
    camera = FakeCameraClient()
    service = CarparkSearchService(registry, camera, FakeInferenceService())

    with pytest.raises(ApplicationError) as error:
        await service.find("user-123", 6)

    assert error.value.status_code == 422
    assert error.value.code == "invalid_n"
    assert registry.sample_calls == []
    assert camera.calls == []
