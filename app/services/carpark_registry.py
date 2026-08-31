import random


MIN_CARPARK_COUNT = 10
MAX_CARPARK_COUNT = 99


class InvalidCarparkCountError(ValueError):
    """Raised when CARPARK_COUNT is outside the assignment's required range."""


class CarparkRegistry:
    """Own the logical car-park IDs available in one SmartPark deployment."""

    def __init__(self, carpark_count: int) -> None:
        if not MIN_CARPARK_COUNT <= carpark_count <= MAX_CARPARK_COUNT:
            raise InvalidCarparkCountError(
                f"CARPARK_COUNT must be between {MIN_CARPARK_COUNT} and "
                f"{MAX_CARPARK_COUNT}"
            )

        self._carpark_ids = tuple(
            f"CBD_{number:03d}" for number in range(1, carpark_count + 1)
        )

    @property
    def count(self) -> int:
        return len(self._carpark_ids)

    def list_ids(self) -> tuple[str, ...]:
        return self._carpark_ids

    def exists(self, carpark_id: str) -> bool:
        return carpark_id in self._carpark_ids

    def sample(self, count: int) -> tuple[str, ...]:
        if count < 0:
            raise ValueError("Sample count cannot be negative")
        if count > self.count:
            raise ValueError("Sample count exceeds the number of car parks")
        return tuple(random.SystemRandom().sample(self._carpark_ids, count))
