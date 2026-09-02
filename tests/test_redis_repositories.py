import pytest

from app.repositories.carpark_status import CarparkStatusRepository
from app.repositories.request_logs import RequestLogRepository
from app.repositories.search_cache import SearchCacheRepository
from app.schemas.search import CarparkSearchResult, RankedCarpark
from tests.fakes import InMemoryRedis


@pytest.mark.anyio
async def test_request_repository_counts_unique_recent_users() -> None:
    redis = InMemoryRedis()
    repository = RequestLogRepository(redis)

    await repository.record_request(
        request_id="request-1",
        uuid="user-a",
        route="/api/find-carparks",
        status_code=200,
        duration_ms=100,
        timestamp=1000,
    )
    await repository.record_request(
        request_id="request-2",
        uuid="user-b",
        route="/api/find-carparks",
        status_code=200,
        duration_ms=120,
        timestamp=1020,
    )
    await repository.record_request(
        request_id="request-3",
        uuid="user-b",
        route="/api/find-carparks",
        status_code=200,
        duration_ms=90,
        timestamp=1040,
    )

    count = await repository.count_unique_users_since(30, now=1050)

    assert count == 1
    assert len(redis.streams[repository.REQUEST_EVENTS_KEY]) == 3


@pytest.mark.anyio
async def test_carpark_status_repository_saves_and_lists_latest() -> None:
    repository = CarparkStatusRepository(InMemoryRedis())

    await repository.save_latest(
        carpark_id="CBD_001",
        available_spaces=42,
        confidence_score=0.94,
        inference_ms=123.4,
        model_version="model-v1",
        updated_at=1000,
    )

    status = await repository.get_latest("CBD_001")
    statuses = await repository.list_latest(("CBD_001", "CBD_002"))

    assert status is not None
    assert status.available_spaces == 42
    assert status.model_version == "model-v1"
    assert statuses == {"CBD_001": status}


@pytest.mark.anyio
async def test_search_cache_round_trip_and_ttl() -> None:
    redis = InMemoryRedis()
    repository = SearchCacheRepository(redis, ttl_seconds=5)
    result = CarparkSearchResult(
        uuid="user-1",
        requested_n=1,
        total_inference_ms=25.0,
        results=(RankedCarpark("CBD_003", 50, 0.95),),
        failed_carparks=0,
    )

    await repository.set(result)
    cached = await repository.get("user-1", 1)

    assert cached == result
    assert redis.expiries["smartpark:search_cache:user-1:1"] == 5


@pytest.mark.anyio
async def test_search_cache_miss_returns_none() -> None:
    repository = SearchCacheRepository(InMemoryRedis(), ttl_seconds=5)

    assert await repository.get("missing-user", 2) is None
