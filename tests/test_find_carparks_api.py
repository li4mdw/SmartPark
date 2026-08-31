from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.core import get_carpark_search_service
from app.main import create_app
from app.services.carpark_search import CarparkSearchResult, RankedCarpark


class FakeModelManager:
    model_version = "test-model"
    model_format = SimpleNamespace(value="pt")

    def load(self) -> None:
        pass


class FakeSearchService:
    async def find(self, uuid: str, n: int) -> CarparkSearchResult:
        assert uuid == "unique-user-id-12345"
        assert n == 2
        return CarparkSearchResult(
            uuid=uuid,
            requested_n=n,
            total_inference_ms=123.456,
            results=(
                RankedCarpark("CBD_003", 71, 0.96),
                RankedCarpark("CBD_009", 63, 0.94),
            ),
            failed_carparks=0,
        )


def make_client() -> TestClient:
    application = create_app(model_manager=FakeModelManager())
    application.dependency_overrides[get_carpark_search_service] = (
        lambda: FakeSearchService()
    )
    return TestClient(application)


def test_find_carparks_returns_assignment_response_shape() -> None:
    with make_client() as client:
        response = client.get(
            "/api/find-carparks",
            params={"uuid": "unique-user-id-12345", "n": 2},
        )

    assert response.status_code == 200
    assert response.json() == {
        "uuid": "unique-user-id-12345",
        "status": "success",
        "msg": "success",
        "speed_inference": "123.46 ms",
        "requested_n": 2,
        "results": [
            {
                "carpark_id": "CBD_003",
                "available_spaces": 71,
                "confidence_score": 0.96,
            },
            {
                "carpark_id": "CBD_009",
                "available_spaces": 63,
                "confidence_score": 0.94,
            },
        ],
    }


def test_find_carparks_rejects_zero_n() -> None:
    with make_client() as client:
        response = client.get(
            "/api/find-carparks",
            params={"uuid": "user-123", "n": 0},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_find_carparks_rejects_unsafe_uuid_characters() -> None:
    with make_client() as client:
        response = client.get(
            "/api/find-carparks",
            params={"uuid": "user id with spaces", "n": 2},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
