from dataclasses import asdict, dataclass
import json
import time
from typing import Any


@dataclass(frozen=True, slots=True)
class StoredCarparkStatus:
    carpark_id: str
    available_spaces: int
    confidence_score: float
    inference_ms: float
    model_version: str
    updated_at: float


class CarparkStatusRepository:
    KEY_PREFIX = "smartpark:carpark_status:"

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def save_latest(
        self,
        *,
        carpark_id: str,
        available_spaces: int,
        confidence_score: float,
        inference_ms: float,
        model_version: str,
        updated_at: float | None = None,
    ) -> None:
        status = StoredCarparkStatus(
            carpark_id=carpark_id,
            available_spaces=available_spaces,
            confidence_score=confidence_score,
            inference_ms=inference_ms,
            model_version=model_version,
            updated_at=updated_at if updated_at is not None else time.time(),
        )
        await self._redis.set(self._key(carpark_id), json.dumps(asdict(status)))

    async def get_latest(self, carpark_id: str) -> StoredCarparkStatus | None:
        value = await self._redis.get(self._key(carpark_id))
        return self._decode(value)

    async def list_latest(
        self,
        carpark_ids: tuple[str, ...],
    ) -> dict[str, StoredCarparkStatus]:
        if not carpark_ids:
            return {}
        values = await self._redis.mget([self._key(item) for item in carpark_ids])
        statuses = (self._decode(value) for value in values)
        return {
            status.carpark_id: status
            for status in statuses
            if status is not None
        }

    @classmethod
    def _key(cls, carpark_id: str) -> str:
        return f"{cls.KEY_PREFIX}{carpark_id}"

    @staticmethod
    def _decode(value: str | None) -> StoredCarparkStatus | None:
        if value is None:
            return None
        return StoredCarparkStatus(**json.loads(value))
