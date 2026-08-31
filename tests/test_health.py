from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.main import create_app


class FakeModelManager:
    model_version = "test-model"
    model_format = SimpleNamespace(value="pt")

    def load(self) -> None:
        pass


def make_app():
    return create_app(model_manager=FakeModelManager())


def test_liveness_endpoint() -> None:
    with TestClient(make_app()) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive", "service": "smartpark-api"}


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
