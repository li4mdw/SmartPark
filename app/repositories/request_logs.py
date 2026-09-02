from dataclasses import dataclass
import time
from typing import Any


@dataclass(frozen=True, slots=True)
class RequestEvent:
    request_id: str
    uuid: str
    route: str
    status_code: int
    duration_ms: float
    timestamp: float


class RequestLogRepository:
    RECENT_USERS_KEY = "smartpark:recent_users"
    REQUEST_EVENTS_KEY = "smartpark:request_events"

    def __init__(self, redis_client: Any, event_limit: int = 10_000) -> None:
        self._redis = redis_client
        self._event_limit = event_limit

    async def record_request(
        self,
        *,
        request_id: str,
        uuid: str,
        route: str,
        status_code: int,
        duration_ms: float,
        timestamp: float | None = None,
    ) -> None:
        event_time = timestamp if timestamp is not None else time.time()
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.zadd(self.RECENT_USERS_KEY, {uuid: event_time})
            pipeline.xadd(
                self.REQUEST_EVENTS_KEY,
                {
                    "request_id": request_id,
                    "uuid": uuid,
                    "route": route,
                    "status_code": str(status_code),
                    "duration_ms": f"{duration_ms:.2f}",
                    "timestamp": f"{event_time:.6f}",
                },
                maxlen=self._event_limit,
                approximate=True,
            )
            await pipeline.execute()

    async def count_unique_users_since(
        self,
        window_seconds: int,
        *,
        now: float | None = None,
    ) -> int:
        current_time = now if now is not None else time.time()
        cutoff = current_time - window_seconds
        async with self._redis.pipeline(transaction=True) as pipeline:
            pipeline.zremrangebyscore(self.RECENT_USERS_KEY, "-inf", cutoff)
            pipeline.zcard(self.RECENT_USERS_KEY)
            _, count = await pipeline.execute()
        return int(count)
