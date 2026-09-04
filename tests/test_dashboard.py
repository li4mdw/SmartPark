from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import create_app
from tests.fakes import InMemoryRedis


class FakeModelManager:
    model_version = "test-model"
    model_format = SimpleNamespace(value="pt")

    def load(self) -> None:
        pass


def test_dashboard_is_served_as_html() -> None:
    application = create_app(
        model_manager=FakeModelManager(),
        redis_client=InMemoryRedis(),
    )

    with TestClient(application) as client:
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "SmartPark Operations" in response.text
    assert "/api/operator/active-users" in response.text
    assert "/api/operator/carparks" in response.text


def test_dashboard_is_not_listed_as_an_api_operation() -> None:
    application = create_app(
        model_manager=FakeModelManager(),
        redis_client=InMemoryRedis(),
    )

    with TestClient(application) as client:
        schema = client.get("/openapi.json").json()

    assert "/dashboard" not in schema["paths"]
