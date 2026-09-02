import logging
from typing import Protocol

import anyio

from app.errors import ApplicationError
from app.infrastructure.concurrency import InferenceExecutor
from app.schemas.search import CarparkSearchResult, RankedCarpark
from app.services.camera_client import CameraClientError
from app.services.inference import InferenceError, InferenceService


logger = logging.getLogger(__name__)


class SearchCameraSource(Protocol):
    async def take_photo(self, carpark_id: str): ...


class SearchCarparkRegistry(Protocol):
    @property
    def count(self) -> int: ...

    def sample(self, count: int) -> tuple[str, ...]: ...


class SearchStatusWriter(Protocol):
    async def save_latest(self, **status) -> None: ...


class CarparkSearchService:
    """Sequential baseline for querying and ranking logical car parks."""

    def __init__(
        self,
        registry: SearchCarparkRegistry,
        camera_client: SearchCameraSource,
        inference_service: InferenceService,
        inference_executor: InferenceExecutor,
        search_timeout_seconds: float,
        status_repository: SearchStatusWriter,
    ) -> None:
        if search_timeout_seconds <= 0:
            raise ValueError("SEARCH_TIMEOUT_SECONDS must be greater than 0")
        self._registry = registry
        self._camera_client = camera_client
        self._inference_service = inference_service
        self._inference_executor = inference_executor
        self._search_timeout_seconds = search_timeout_seconds
        self._status_repository = status_repository

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

        async def scan_carpark(carpark_id: str) -> None:
            nonlocal total_inference_ms, failed_carparks
            try:
                photo = await self._camera_client.take_photo(carpark_id)
                inference = await self._inference_executor.run(
                    self._inference_service.predict,
                    photo.content,
                    include_annotation=False,
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
                return

            successful.append(
                RankedCarpark(
                    carpark_id=carpark_id,
                    available_spaces=inference.available_spaces,
                    confidence_score=inference.confidence_score,
                )
            )
            total_inference_ms += inference.inference_ms
            try:
                await self._status_repository.save_latest(
                    carpark_id=carpark_id,
                    available_spaces=inference.available_spaces,
                    confidence_score=inference.confidence_score,
                    inference_ms=inference.inference_ms,
                    model_version=inference.model_version,
                )
            except Exception:
                # Search results remain useful if only the operational store fails.
                logger.exception(
                    "carpark_status_write_failed",
                    extra={"uuid": uuid, "carpark_id": carpark_id},
                )

        try:
            with anyio.fail_after(self._search_timeout_seconds):
                async with anyio.create_task_group() as task_group:
                    for carpark_id in selected_ids:
                        task_group.start_soon(scan_carpark, carpark_id)
        except TimeoutError as exc:
            raise ApplicationError(
                status_code=504,
                code="search_timeout",
                message="The car-park search exceeded its time limit",
            ) from exc

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
