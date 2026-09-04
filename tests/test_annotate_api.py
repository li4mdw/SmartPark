import base64
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.core import get_annotation_service
from app.main import create_app
from app.services.annotation import AnnotationResult
from tests.fakes import InMemoryRedis


class FakeModelManager:
    model_version = "test-model"
    model_format = SimpleNamespace(value="pt")

    def load(self) -> None:
        pass


class FakeAnnotationService:
    async def annotate(self, carpark_id: str) -> AnnotationResult:
        return AnnotationResult(carpark_id=carpark_id, image=b"annotated-jpeg")


def make_client() -> TestClient:
    application = create_app(
        model_manager=FakeModelManager(), redis_client=InMemoryRedis()
    )
    application.dependency_overrides[get_annotation_service] = (
        lambda: FakeAnnotationService()
    )
    return TestClient(application)


def test_annotate_endpoint_returns_specification_response() -> None:
    with make_client() as client:
        response = client.get(
            "/api/annotate-carpark",
            params={"carpark_id": "CBD_007"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "carpark_id": "CBD_007",
        "status": "success",
        "msg": "success",
        "image_base64": base64.b64encode(b"annotated-jpeg").decode("ascii"),
    }


def test_annotate_endpoint_rejects_invalid_id_format() -> None:
    with make_client() as client:
        response = client.get(
            "/api/annotate-carpark",
            params={"carpark_id": "invalid"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_annotate_endpoint_rejects_id_outside_configured_range() -> None:
    application = create_app(
        model_manager=FakeModelManager(), redis_client=InMemoryRedis()
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/annotate-carpark",
            params={"carpark_id": "CBD_011"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "status": "error",
        "msg": "The requested car park does not exist",
        "error": {"code": "carpark_not_found"},
    }


def test_annotate_request_is_logged_and_uuid_counts_as_active_user() -> None:
    redis = InMemoryRedis()
    application = create_app(
        model_manager=FakeModelManager(), redis_client=redis
    )
    application.dependency_overrides[get_annotation_service] = (
        lambda: FakeAnnotationService()
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/annotate-carpark",
            params={"carpark_id": "CBD_007", "uuid": "user-annotate-1"},
            headers={"x-request-id": "annotation-request-1"},
        )

    assert response.status_code == 200
    assert redis.sorted_sets["smartpark:recent_users"].keys() == {
        "user-annotate-1"
    }
    event = redis.streams["smartpark:request_events"][0]
    assert event["route"] == "/api/annotate-carpark"
    assert event["uuid"] == "user-annotate-1"


def test_annotate_without_uuid_is_logged_without_creating_a_user() -> None:
    redis = InMemoryRedis()
    application = create_app(
        model_manager=FakeModelManager(), redis_client=redis
    )
    application.dependency_overrides[get_annotation_service] = (
        lambda: FakeAnnotationService()
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/annotate-carpark",
            params={"carpark_id": "CBD_007"},
        )

    assert response.status_code == 200
    assert not redis.sorted_sets["smartpark:recent_users"]
    event = redis.streams["smartpark:request_events"][0]
    assert event["route"] == "/api/annotate-carpark"
    assert event["uuid"] == ""
