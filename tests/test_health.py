from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.main import create_app
from tests.fakes import InMemoryRedis


class FakeModelManager:
    model_version = "test-model"
    model_format = SimpleNamespace(value="pt")
    model_path = "test-model.pt"
    is_loaded = True

    def load(self) -> None:
        pass


def make_app():
    return create_app(
        model_manager=FakeModelManager(),
        redis_client=InMemoryRedis(),
    )


def test_liveness_endpoint() -> None:
    with TestClient(make_app()) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "service": "smartpark-api"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_readiness_endpoint_after_startup() -> None:
    with TestClient(make_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "smartpark-api"}


def test_readiness_endpoint_before_startup() -> None:
    client = TestClient(make_app())
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "smartpark-api",
    }


def test_readiness_fails_when_model_is_not_loaded() -> None:
    application = make_app()

    with TestClient(application) as client:
        application.state.model_manager.is_loaded = False
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
