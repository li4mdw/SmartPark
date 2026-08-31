import pytest

from app.services.carpark_registry import (
    CarparkRegistry,
    InvalidCarparkCountError,
)


def test_registry_generates_expected_ids() -> None:
    registry = CarparkRegistry(10)

    assert registry.count == 10
    assert registry.list_ids() == (
        "CBD_001",
        "CBD_002",
        "CBD_003",
        "CBD_004",
        "CBD_005",
        "CBD_006",
        "CBD_007",
        "CBD_008",
        "CBD_009",
        "CBD_010",
    )


@pytest.mark.parametrize("count", [9, 100, 0, -1])
def test_registry_rejects_count_outside_required_range(count: int) -> None:
    with pytest.raises(InvalidCarparkCountError, match="between 10 and 99"):
        CarparkRegistry(count)


def test_registry_checks_membership() -> None:
    registry = CarparkRegistry(10)

    assert registry.exists("CBD_001") is True
    assert registry.exists("CBD_010") is True
    assert registry.exists("CBD_000") is False
    assert registry.exists("CBD_011") is False
    assert registry.exists("CBD_999") is False


def test_registry_sample_is_unique_and_valid() -> None:
    registry = CarparkRegistry(20)

    sample = registry.sample(12)

    assert len(sample) == 12
    assert len(set(sample)) == 12
    assert all(registry.exists(carpark_id) for carpark_id in sample)


def test_registry_rejects_sample_larger_than_range() -> None:
    registry = CarparkRegistry(10)

    with pytest.raises(ValueError, match="exceeds"):
        registry.sample(11)
