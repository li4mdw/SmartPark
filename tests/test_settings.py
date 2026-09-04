from app.infrastructure.settings import Settings
import pytest


def test_environment_loader_uses_declared_cache_ttl_default(monkeypatch) -> None:
    monkeypatch.delenv("SEARCH_CACHE_TTL_SECONDS", raising=False)

    settings = Settings.from_environment()

    assert settings.search_cache_ttl_seconds == Settings().search_cache_ttl_seconds
    assert settings.search_cache_ttl_seconds == 30


def test_environment_can_override_cache_ttl(monkeypatch) -> None:
    monkeypatch.setenv("SEARCH_CACHE_TTL_SECONDS", "45")

    settings = Settings.from_environment()

    assert settings.search_cache_ttl_seconds == 45


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("carpark_count", 9, "CARPARK_COUNT"),
        ("camera_concurrency", 0, "CAMERA_CONCURRENCY"),
        ("search_timeout_seconds", 0, "SEARCH_TIMEOUT_SECONDS"),
        ("redis_url", "http://redis:6379", "REDIS_URL"),
        ("camera_base_url", "redis://camera:8001", "CAMERA_BASE_URL"),
        ("model_version", "", "MODEL_VERSION"),
    ],
)
def test_invalid_settings_fail_early(field, value, message) -> None:
    values = {field: value}

    with pytest.raises(ValueError, match=message):
        Settings(**values)
