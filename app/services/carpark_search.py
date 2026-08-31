from dataclasses import dataclass
from functools import partial
import logging
from typing import Protocol

import anyio

from app.errors import ApplicationError
from app.services.camera_client import CameraClientError
from app.services.inference import InferenceError, InferenceService


logger = logging.getLogger(__name__)


class SearchCameraSource(Protocol):
    async def take_photo(self, carpark_id: str): ...


class SearchCarparkRegistry(Protocol):
    @property
    def count(self) -> int: ...

    def sample(self, count: int) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class RankedCarpark:
    carpark_id: str
    available_spaces: int
    confidence_score: float


@dataclass(frozen=True, slots=True)
class CarparkSearchResult:
    uuid: str
    requested_n: int
    total_inference_ms: float
    results: tuple[RankedCarpark, ...]
    failed_carparks: int


class CarparkSearchService:
    """Sequential baseline for querying and ranking logical car parks."""

    def __init__(
        self,
        registry: SearchCarparkRegistry,
        camera_client: SearchCameraSource,
        inference_service: InferenceService,
    ) -> None:
        self._registry = registry
        self._camera_client = camera_client
        self._inference_service = inference_service

    async def find(self, uuid: str, n: int) -> CarparkSearchResult:
        query_count = 2 * n
        if query_count > self._registry.count:
            maximum_n = self._registry.count // 2
            raise ApplicationError(
                status_code=422,
                code="invalid_n",
                message=(
                    f"n must be between 1 and {maximum_n} because at least "
                    "2 × n car parks must be queried"
                ),
            )

        selected_ids = self._registry.sample(query_count)
        successful: list[RankedCarpark] = []
        total_inference_ms = 0.0
        failed_carparks = 0

        for carpark_id in selected_ids:
            try:
                photo = await self._camera_client.take_photo(carpark_id)
                inference = await anyio.to_thread.run_sync(
                    partial(
                        self._inference_service.predict,
                        photo.content,
                        include_annotation=False,
                    )
                )
            except (CameraClientError, InferenceError) as exc:
                failed_carparks += 1
                logger.warning(
                    "carpark_scan_failed",
                    extra={
                        "uuid": uuid,
                        "carpark_id": carpark_id,
                        "error_type": type(exc).__name__,
                    },
                )
                continue

            successful.append(
                RankedCarpark(
                    carpark_id=carpark_id,
                    available_spaces=inference.available_spaces,
                    confidence_score=inference.confidence_score,
                )
            )
            total_inference_ms += inference.inference_ms

        if len(successful) < n:
            raise ApplicationError(
                status_code=503,
                code="insufficient_carpark_results",
                message="Too few car parks could be processed to satisfy the request",
            )

        ranked = sorted(
            successful,
            key=lambda item: (
                -item.available_spaces,
                -item.confidence_score,
                item.carpark_id,
            ),
        )
        top_results = tuple(ranked[:n])

        logger.info(
            "carpark_search_completed",
            extra={
                "uuid": uuid,
                "requested_n": n,
                "queried_carparks": query_count,
                "successful_carparks": len(successful),
                "failed_carparks": failed_carparks,
                "inference_ms": round(total_inference_ms, 2),
            },
        )
        return CarparkSearchResult(
            uuid=uuid,
            requested_n=n,
            total_inference_ms=round(total_inference_ms, 2),
            results=top_results,
            failed_carparks=failed_carparks,
        )
