from types import SimpleNamespace
from functools import partial

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.carpark_status import CarparkStatusRepository
from tests.fakes import InMemoryRedis


class FakeModelManager:
    model_version = "test-model"
    model_format = SimpleNamespace(value="pt")

    def load(self) -> None:
        pass


def test_operator_carparks_returns_known_and_unknown_statuses() -> None:
    redis = InMemoryRedis()
    application = create_app(
        model_manager=FakeModelManager(),
        redis_client=redis,
    )

    with TestClient(application) as client:
        status_repository = CarparkStatusRepository(redis)
        client.portal.call(partial(
            status_repository.save_latest,
            carpark_id="CBD_001",
            available_spaces=12,
            confidence_score=0.93,
            inference_ms=20.5,
            model_version="test-model",
            updated_at=1000,
        ))
        response = client.get("/api/operator/carparks")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["carparks"]) == 10
    assert payload["carparks"][0] == {
        "carpark_id": "CBD_001",
        "status": "known",
        "available_spaces": 12,
        "confidence_score": 0.93,
        "inference_ms": 20.5,
        "model_version": "test-model",
        "updated_at": 1000.0,
    }
    assert payload["carparks"][1]["status"] == "unknown"
    assert payload["carparks"][1]["available_spaces"] is None


def test_operator_active_users_counts_unique_recent_find_requests() -> None:
    redis = InMemoryRedis()
    application = create_app(
        model_manager=FakeModelManager(),
        redis_client=redis,
    )

    with TestClient(application) as client:
        now = __import__("time").time()
        redis.sorted_sets["smartpark:recent_users"] = {
            "user-a": now,
            "user-b": now,
            "expired-user": now - 31,
        }
        response = client.get("/api/operator/active-users")

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "msg": "success",
        "window_seconds": 30,
        "active_users": 2,
    }
