from dataclasses import asdict
import json
from typing import Any

from app.schemas.search import CarparkSearchResult, RankedCarpark


class SearchCacheRepository:
    KEY_PREFIX = "smartpark:search_cache:"

    def __init__(
        self,
        redis_client: Any,
        ttl_seconds: int,
        model_version: str = "model-v1",
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("SEARCH_CACHE_TTL_SECONDS must be at least 1")
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds
        self._model_version = model_version

    async def get(self, uuid: str, n: int) -> CarparkSearchResult | None:
        value = await self._redis.get(self._key(uuid, n))
        if value is None:
            return None
        payload = json.loads(value)
        payload["results"] = tuple(RankedCarpark(**item) for item in payload["results"])
        return CarparkSearchResult(**payload)

    async def set(self, result: CarparkSearchResult) -> None:
        await self._redis.set(
            self._key(result.uuid, result.requested_n),
            json.dumps(asdict(result)),
            ex=self._ttl_seconds,
        )

    def _key(self, uuid: str, n: int) -> str:
        return f"{self.KEY_PREFIX}{self._model_version}:{uuid}:{n}"
