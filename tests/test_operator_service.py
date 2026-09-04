import pytest

from app.errors import ApplicationError
from app.repositories.carpark_status import CarparkStatusRepository
from app.repositories.request_logs import RequestLogRepository
from app.services.carpark_registry import CarparkRegistry
from app.services.operator import OperatorService
from tests.fakes import InMemoryRedis


@pytest.mark.anyio
async def test_operator_service_lists_every_configured_carpark() -> None:
    redis = InMemoryRedis()
    statuses = CarparkStatusRepository(redis)
    requests = RequestLogRepository(redis)
    service = OperatorService(CarparkRegistry(10), statuses, requests, 30)
    await statuses.save_latest(
        carpark_id="CBD_002",
        available_spaces=17,
        confidence_score=0.91,
        inference_ms=25.0,
        model_version="model-v1",
        updated_at=1000,
    )

    result = await service.list_carparks()

    assert len(result) == 10
    assert result[0].carpark_id == "CBD_001"
    assert result[0].stored_status is None
    assert result[1].stored_status is not None
    assert result[1].stored_status.available_spaces == 17


@pytest.mark.anyio
async def test_operator_service_counts_users_in_configured_window() -> None:
    class RequestReader:
        async def count_unique_users_since(self, window_seconds: int) -> int:
            assert window_seconds == 30
            return 4

    service = OperatorService(
        CarparkRegistry(10), CarparkStatusRepository(InMemoryRedis()), RequestReader(), 30
    )

    assert await service.count_active_users() == 4


@pytest.mark.anyio
async def test_operator_service_maps_redis_failure_to_503() -> None:
    class BrokenStatusReader:
        async def list_latest(self, carpark_ids):
            raise ConnectionError("Redis unavailable")

    service = OperatorService(
        CarparkRegistry(10), BrokenStatusReader(), RequestLogRepository(InMemoryRedis()), 30
    )

    with pytest.raises(ApplicationError) as error:
        await service.list_carparks()

    assert error.value.status_code == 503
    assert error.value.code == "operational_store_unavailable"
