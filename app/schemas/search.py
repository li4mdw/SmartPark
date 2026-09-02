from dataclasses import dataclass


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
