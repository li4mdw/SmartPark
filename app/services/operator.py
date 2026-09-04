from dataclasses import dataclass
from typing import Protocol

from app.errors import ApplicationError
from app.repositories.carpark_status import StoredCarparkStatus


class OperatorCarparkRegistry(Protocol):
    def list_ids(self) -> tuple[str, ...]: ...


class OperatorStatusReader(Protocol):
    async def list_latest(
        self,
        carpark_ids: tuple[str, ...],
    ) -> dict[str, StoredCarparkStatus]: ...


class OperatorRequestLogReader(Protocol):
    async def count_unique_users_since(self, window_seconds: int) -> int: ...


@dataclass(frozen=True, slots=True)
class OperatorCarpark:
    carpark_id: str
    stored_status: StoredCarparkStatus | None


class OperatorService:
    def __init__(
        self,
        carpark_registry: OperatorCarparkRegistry,
        status_repository: OperatorStatusReader,
        request_log_repository: OperatorRequestLogReader,
        recent_user_window_seconds: int,
    ) -> None:
        self._carpark_registry = carpark_registry
        self._status_repository = status_repository
        self._request_log_repository = request_log_repository
        self.recent_user_window_seconds = recent_user_window_seconds

    async def list_carparks(self) -> tuple[OperatorCarpark, ...]:
        carpark_ids = self._carpark_registry.list_ids()
        try:
            stored = await self._status_repository.list_latest(carpark_ids)
        except Exception as exc:
            raise self._store_unavailable() from exc

        return tuple(
            OperatorCarpark(carpark_id, stored.get(carpark_id))
            for carpark_id in carpark_ids
        )

    async def count_active_users(self) -> int:
        try:
            return await self._request_log_repository.count_unique_users_since(
                self.recent_user_window_seconds
            )
        except Exception as exc:
            raise self._store_unavailable() from exc

    @staticmethod
    def _store_unavailable() -> ApplicationError:
        return ApplicationError(
            status_code=503,
            code="operational_store_unavailable",
            message="Operational data is temporarily unavailable",
        )
