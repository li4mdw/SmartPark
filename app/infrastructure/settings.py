from dataclasses import dataclass
import logging
import os
from pathlib import Path
from urllib.parse import urlparse


_RELEASE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEARCH_CACHE_TTL_SECONDS = 30


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "SmartPark API"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    model_path: Path = _RELEASE_ROOT / "model" / "model.pt"
    model_version: str = "model-v1"
    available_class_id: int = 0
    max_image_bytes: int = 10 * 1024 * 1024
    camera_base_url: str = "http://127.0.0.1:8001"
    camera_connect_timeout_seconds: float = 2.0
    camera_read_timeout_seconds: float = 10.0
    carpark_count: int = 10
    camera_concurrency: int = 10
    inference_concurrency: int = 1
    search_timeout_seconds: float = 60.0
    redis_url: str = "redis://127.0.0.1:6379/0"
    recent_user_window_seconds: int = 30
    search_cache_ttl_seconds: int = DEFAULT_SEARCH_CACHE_TTL_SECONDS

    def __post_init__(self) -> None:
        if self.log_level not in logging._nameToLevel:
            raise ValueError("LOG_LEVEL must be a valid Python logging level")
        if not self.model_version.strip():
            raise ValueError("MODEL_VERSION cannot be empty")
        if self.available_class_id < 0:
            raise ValueError("AVAILABLE_CLASS_ID cannot be negative")
        if self.max_image_bytes < 1:
            raise ValueError("MAX_IMAGE_BYTES must be at least 1")
        if not 10 <= self.carpark_count <= 99:
            raise ValueError("CARPARK_COUNT must be between 10 and 99")

        positive_values = {
            "CAMERA_CONNECT_TIMEOUT_SECONDS": self.camera_connect_timeout_seconds,
            "CAMERA_READ_TIMEOUT_SECONDS": self.camera_read_timeout_seconds,
            "CAMERA_CONCURRENCY": self.camera_concurrency,
            "INFERENCE_CONCURRENCY": self.inference_concurrency,
            "SEARCH_TIMEOUT_SECONDS": self.search_timeout_seconds,
            "RECENT_USER_WINDOW_SECONDS": self.recent_user_window_seconds,
            "SEARCH_CACHE_TTL_SECONDS": self.search_cache_ttl_seconds,
        }
        for name, value in positive_values.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than 0")

        self._validate_url("CAMERA_BASE_URL", self.camera_base_url, {"http", "https"})
        self._validate_url("REDIS_URL", self.redis_url, {"redis", "rediss"})

    @staticmethod
    def _validate_url(name: str, value: str, schemes: set[str]) -> None:
        parsed = urlparse(value)
        if parsed.scheme not in schemes or not parsed.hostname:
            allowed = ", ".join(sorted(schemes))
            raise ValueError(f"{name} must use {allowed} and include a hostname")

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "SmartPark API"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            environment=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            model_path=Path(
                os.getenv("MODEL_PATH", str(_RELEASE_ROOT / "model" / "model.pt"))
            ),
            model_version=os.getenv("MODEL_VERSION", "model-v1"),
            available_class_id=int(os.getenv("AVAILABLE_CLASS_ID", "0")),
            max_image_bytes=int(os.getenv("MAX_IMAGE_BYTES", str(10 * 1024 * 1024))),
            camera_base_url=os.getenv("CAMERA_BASE_URL", "http://127.0.0.1:8001"),
            camera_connect_timeout_seconds=float(
                os.getenv("CAMERA_CONNECT_TIMEOUT_SECONDS", "2.0")
            ),
            camera_read_timeout_seconds=float(
                os.getenv("CAMERA_READ_TIMEOUT_SECONDS", "10.0")
            ),
            carpark_count=int(os.getenv("CARPARK_COUNT", "10")),
            camera_concurrency=int(os.getenv("CAMERA_CONCURRENCY", "10")),
            inference_concurrency=int(os.getenv("INFERENCE_CONCURRENCY", "1")),
            search_timeout_seconds=float(os.getenv("SEARCH_TIMEOUT_SECONDS", "60.0")),
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            recent_user_window_seconds=int(
                os.getenv("RECENT_USER_WINDOW_SECONDS", "30")
            ),
            search_cache_ttl_seconds=int(
                os.getenv(
                    "SEARCH_CACHE_TTL_SECONDS",
                    str(DEFAULT_SEARCH_CACHE_TTL_SECONDS),
                )
            ),
        )
