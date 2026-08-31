from dataclasses import dataclass
import os
from pathlib import Path


_RELEASE_ROOT = Path(__file__).resolve().parents[2]


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
        )
