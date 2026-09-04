from app.infrastructure.settings import Settings


def test_environment_loader_uses_declared_cache_ttl_default(monkeypatch) -> None:
    monkeypatch.delenv("SEARCH_CACHE_TTL_SECONDS", raising=False)

    settings = Settings.from_environment()

    assert settings.search_cache_ttl_seconds == Settings().search_cache_ttl_seconds
    assert settings.search_cache_ttl_seconds == 30


def test_environment_can_override_cache_ttl(monkeypatch) -> None:
    monkeypatch.setenv("SEARCH_CACHE_TTL_SECONDS", "45")

    settings = Settings.from_environment()

    assert settings.search_cache_ttl_seconds == 45
